"""
Rate Limit Checker, Analysis, and Adaptive Scheduling Engine.
- Centralized request telemetry across crawler workers and API.
- Shared persistence in MongoDB (rate_limit_request_logs, domain_rate_profiles, rate_limit_events, api_rate_limit_profiles).
- Response classification: SUCCESS, REDIRECT, RATE_LIMITED, ACCESS_FORBIDDEN, BOT_PROTECTION, AUTHENTICATION_ERROR, SERVER_ERROR, NETWORK_ERROR, TIMEOUT, UNKNOWN.
- Header parser for Retry-After (seconds & HTTP-date in UTC), RateLimit-*, X-RateLimit-*.
- Conservative request frequency recommendation & confidence grading.
- Adaptive request control: domain cooldown, exponential backoff with jitter, concurrency management.
- Mode B: GitHub API Provider integration with dynamic quota tracking and secure secret masking.
"""
import asyncio
import csv
import io
import logging
import random
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import httpx

logger = logging.getLogger(__name__)


class ResponseClassifier:
    @staticmethod
    def classify(
        status_code: Optional[int],
        headers: Dict[str, str],
        error_type: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Classifies response into structured categories and explains the classification reason.
        """
        headers_lower = {k.lower(): v for k, v in headers.items()}

        if error_type:
            err_lower = error_type.lower()
            if "timeout" in err_lower:
                return "TIMEOUT", f"Client/Network timeout: {error_type}"
            if "connect" in err_lower or "dns" in err_lower or "network" in err_lower:
                return "NETWORK_ERROR", f"Network resolution failure: {error_type}"

        if status_code is None:
            return "NETWORK_ERROR", error_type or "No response received"

        # Rate Limiting
        if status_code == 429:
            return "RATE_LIMITED", "HTTP 429 Too Many Requests response"

        # Retry-After header presence with 403 or 503
        if "retry-after" in headers_lower and status_code in (403, 503):
            return "RATE_LIMITED", f"HTTP {status_code} with explicit Retry-After header"

        # Bot Protection / Cloudflare
        server_header = headers_lower.get("server", "").lower()
        if status_code == 403:
            if "cloudflare" in server_header or "cf-ray" in headers_lower:
                return "BOT_PROTECTION", "Cloudflare / CDN WAF challenge response (403)"
            return "ACCESS_FORBIDDEN", "HTTP 403 Forbidden without rate-limit indication"

        if status_code == 401:
            return "AUTHENTICATION_ERROR", "HTTP 401 Unauthorized"

        if status_code == 408:
            return "TIMEOUT", "HTTP 408 Request Timeout"

        if 300 <= status_code < 400:
            return "REDIRECT", f"HTTP {status_code} Redirect"

        if 200 <= status_code < 300:
            return "SUCCESS", f"HTTP {status_code} OK"

        if 500 <= status_code < 600:
            return "SERVER_ERROR", f"HTTP {status_code} Server Error"

        return "UNKNOWN", f"HTTP {status_code} Unclassified"


class HeaderAnalyzer:
    @staticmethod
    def parse_retry_after(header_value: Optional[str]) -> Optional[int]:
        """
        Parses Retry-After header. Supports:
        1. Seconds numeric integer
        2. HTTP-date format (RFC 2822) converted to UTC delay seconds
        """
        if not header_value:
            return None
        val = header_value.strip()
        try:
            return max(1, int(val))
        except ValueError:
            pass

        try:
            dt = parsedate_to_datetime(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delay = (dt - now).total_seconds()
            return max(1, int(delay))
        except Exception:
            return None

    @staticmethod
    def extract_rate_limit_headers(headers: Dict[str, str]) -> Dict[str, str]:
        relevant = {}
        for k, v in headers.items():
            kl = k.lower()
            if any(h in kl for h in ["ratelimit", "retry-after", "cf-ray", "server", "x-github"]):
                relevant[k] = v
        return relevant


class RateLimitService:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self._lock = asyncio.Lock()

    @property
    def database(self) -> Optional[Any]:
        if self.db is not None:
            return self.db
        try:
            from app.database.connection import get_database
            return get_database()
        except Exception:
            return None

    def _get_domain(self, url_or_domain: str) -> str:
        if "://" in url_or_domain:
            parsed = urlparse(url_or_domain)
            return (parsed.netloc or "").lower().split(":")[0]
        return url_or_domain.lower().split(":")[0]

    # --- Mode A: Request Monitoring & Telemetry Recording ---
    async def record_request_metric(
        self,
        url_or_domain: str,
        status_code: Optional[int],
        response_time_ms: float,
        headers: Optional[Dict[str, str]] = None,
        error_type: Optional[str] = None,
        method: str = "GET",
        endpoint: Optional[str] = None,
        session_id: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Intercepts outgoing crawler request result, classifies response, updates MongoDB domain profile,
        and logs to rate_limit_request_logs.
        """
        domain = self._get_domain(url_or_domain)
        headers = headers or {}
        now = datetime.now(timezone.utc)

        classification, class_reason = ResponseClassifier.classify(status_code, headers, error_type)
        retry_after_val = HeaderAnalyzer.parse_retry_after(headers.get("Retry-After") or headers.get("retry-after"))
        rl_headers = HeaderAnalyzer.extract_rate_limit_headers(headers)

        is_throttled = classification in ("RATE_LIMITED", "BOT_PROTECTION")
        is_success = classification == "SUCCESS"

        # Log item
        log_doc = {
            "session_id": session_id,
            "worker_id": worker_id,
            "domain": domain,
            "endpoint": endpoint or url_or_domain,
            "method": method,
            "timestamp": now,
            "status_code": status_code,
            "classification": classification,
            "response_time_ms": round(response_time_ms, 2),
            "retry_after": retry_after_val,
            "relevant_headers": rl_headers,
            "error_reason": error_type or class_reason,
        }

        # 1. Persist to MongoDB rate_limit_request_logs
        db = self.database
        if db is not None:
            try:
                await db.rate_limit_request_logs.insert_one(dict(log_doc))
                # Also keep legacy collection in sync
                await db.rate_limit_metrics.insert_one({
                    "domain": domain,
                    "timestamp": now,
                    "status_code": status_code,
                    "response_time_ms": round(response_time_ms, 2),
                    "is_throttled": is_throttled,
                    "retry_after": retry_after_val,
                    "rate_limit_headers": rl_headers,
                    "error_type": error_type,
                    "action_taken": classification,
                })
            except Exception as e:
                logger.debug("Failed to insert request log into MongoDB: %s", e)

        # 2. Update / Upsert domain profile in MongoDB
        if db is not None:
            try:
                profile = await db.domain_rate_profiles.find_one({"domain": domain})
                if not profile:
                    profile = {
                        "domain": domain,
                        "provider_type": "website",
                        "policy_scope": "domain",
                        "estimated_interval_ms": 1000.0,
                        "active_interval_ms": 1000.0,
                        "active_concurrency": 3,
                        "successful_requests": 0,
                        "blocked_requests": 0,
                        "total_requests": 0,
                        "blocking_percentage": 0.0,
                        "average_response_time": response_time_ms,
                        "confidence": "INSUFFICIENT DATA",
                        "status": "normal",
                        "cooldown_until": None,
                        "is_paused": False,
                        "last_observed_at": now,
                        "updated_at": now,
                    }

                total = profile.get("total_requests", 0) + 1
                succ = profile.get("successful_requests", 0) + (1 if is_success else 0)
                blocked = profile.get("blocked_requests", 0) + (1 if is_throttled else 0)
                blocking_pct = round((blocked / total) * 100, 2)

                prev_avg = profile.get("average_response_time", response_time_ms)
                new_avg = round(((prev_avg * (total - 1)) + response_time_ms) / total, 2)

                # Confidence grading
                confidence = "INSUFFICIENT DATA"
                if total >= 100:
                    confidence = "HIGH CONFIDENCE"
                elif total >= 30:
                    confidence = "MEDIUM CONFIDENCE"
                elif total >= 5:
                    confidence = "LOW CONFIDENCE"

                # Adaptive delay and status adjustment
                status = profile.get("status", "normal")
                cooldown_until = profile.get("cooldown_until")
                current_interval = profile.get("active_interval_ms", 1000.0)
                current_concurrency = profile.get("active_concurrency", 3)

                if is_throttled:
                    status = "cautious" if blocked <= 2 else "attention_required"
                    jitter_ms = random.uniform(200, 800)
                    if retry_after_val:
                        cooldown_sec = retry_after_val
                        cooldown_until = now + timedelta(seconds=cooldown_sec)
                        current_interval = max(current_interval, (cooldown_sec * 1000.0) + jitter_ms)
                    else:
                        cooldown_sec = min(30, 2 ** min(blocked, 5))
                        cooldown_until = now + timedelta(seconds=cooldown_sec)
                        current_interval = min(30000.0, (current_interval * 1.5) + jitter_ms)

                    current_concurrency = max(1, current_concurrency - 1)

                    # Record incident in rate_limit_events
                    await db.rate_limit_events.insert_one({
                        "domain": domain,
                        "event_type": "rate_limited",
                        "severity": "warning" if blocked <= 2 else "critical",
                        "reason": f"HTTP {status_code} ({classification})",
                        "cooldown_until": cooldown_until,
                        "details": {"retry_after": retry_after_val, "status_code": status_code},
                        "timestamp": now,
                    })
                elif is_success:
                    # Gradual healing
                    if current_interval > 1000.0 and random.random() < 0.2:
                        current_interval = max(1000.0, current_interval * 0.9)
                        current_concurrency = min(5, current_concurrency + 1)
                    if blocking_pct < 5.0 and not profile.get("is_paused"):
                        status = "normal"

                estimated_interval = current_interval * 1.1

                await db.domain_rate_profiles.update_one(
                    {"domain": domain},
                    {
                        "$set": {
                            "total_requests": total,
                            "successful_requests": succ,
                            "blocked_requests": blocked,
                            "blocking_percentage": blocking_pct,
                            "average_response_time": new_avg,
                            "confidence": confidence,
                            "status": status,
                            "active_interval_ms": round(current_interval, 1),
                            "estimated_interval_ms": round(estimated_interval, 1),
                            "active_concurrency": current_concurrency,
                            "cooldown_until": cooldown_until,
                            "last_observed_at": now,
                            "updated_at": now,
                        }
                    },
                    upsert=True,
                )
            except Exception as e:
                logger.debug("Failed to update domain rate profile: %s", e)

        return log_doc

    # --- Mode A: Domain Policy Recommendation & Shared State ---
    async def get_domain_policy(self, url_or_domain: str) -> Dict[str, Any]:
        """
        Returns authoritative scheduling policy for crawler execution.
        """
        domain = self._get_domain(url_or_domain)
        db = self.database
        if db is not None:
            profile = await db.domain_rate_profiles.find_one({"domain": domain})
            if isinstance(profile, dict):
                now = datetime.now(timezone.utc)
                cd = profile.get("cooldown_until")
                is_in_cooldown = False
                if isinstance(cd, datetime):
                    if cd.tzinfo is None:
                        cd = cd.replace(tzinfo=timezone.utc)
                    is_in_cooldown = bool(cd > now)
                elif isinstance(cd, str):
                    try:
                        cd_dt = datetime.fromisoformat(cd)
                        if cd_dt.tzinfo is None:
                            cd_dt = cd_dt.replace(tzinfo=timezone.utc)
                        is_in_cooldown = bool(cd_dt > now)
                    except Exception:
                        pass
                delay_sec = max(1.0, float(profile.get("active_interval_ms", 1000.0) or 1000.0) / 1000.0)
                return {
                    "domain": domain,
                    "recommended_delay_seconds": round(delay_sec, 2),
                    "active_interval_ms": profile.get("active_interval_ms", 1000.0),
                    "estimated_interval_ms": profile.get("estimated_interval_ms", 1000.0),
                    "max_concurrency": profile.get("active_concurrency", 3),
                    "confidence": profile.get("confidence", "INSUFFICIENT DATA"),
                    "status": profile.get("status", "normal"),
                    "is_paused": profile.get("is_paused", False),
                    "is_in_cooldown": is_in_cooldown,
                    "cooldown_until": cd.isoformat() if cd else None,
                }

        return {
            "domain": domain,
            "recommended_delay_seconds": 1.5,
            "active_interval_ms": 1500.0,
            "estimated_interval_ms": 1500.0,
            "max_concurrency": 3,
            "confidence": "INSUFFICIENT DATA",
            "status": "normal",
            "is_paused": False,
            "is_in_cooldown": False,
            "cooldown_until": None,
        }

    # --- Mode A: Global Telemetry & Domain Breakdown ---
    async def get_summary_metrics(self) -> Dict[str, Any]:
        """
        Aggregates live metrics from MongoDB across all requests and domains.
        """
        total_reqs = 0
        total_succ = 0
        total_throttled = 0
        total_forbidden = 0
        total_errors = 0
        avg_resp_time = 0.0
        monitored_domains = 0
        paused_domains = 0

        db = self.database
        if db is not None:
            try:
                monitored_domains = await db.domain_rate_profiles.count_documents({})
                paused_domains = await db.domain_rate_profiles.count_documents({"is_paused": True})

                pipeline = [
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": 1},
                            "success": {"$sum": {"$cond": [{"$eq": ["$classification", "SUCCESS"]}, 1, 0]}},
                            "throttled": {"$sum": {"$cond": [{"$eq": ["$classification", "RATE_LIMITED"]}, 1, 0]}},
                            "forbidden": {"$sum": {"$cond": [{"$eq": ["$classification", "ACCESS_FORBIDDEN"]}, 1, 0]}},
                            "bot_waf": {"$sum": {"$cond": [{"$eq": ["$classification", "BOT_PROTECTION"]}, 1, 0]}},
                            "avg_time": {"$avg": "$response_time_ms"},
                        }
                    }
                ]
                agg_res = await db.rate_limit_request_logs.aggregate(pipeline).to_list(1)
                if agg_res:
                    row = agg_res[0]
                    total_reqs = row.get("total", 0)
                    total_succ = row.get("success", 0)
                    total_throttled = row.get("throttled", 0) + row.get("bot_waf", 0)
                    total_forbidden = row.get("forbidden", 0)
                    total_errors = max(0, total_reqs - total_succ)
                    avg_resp_time = round(row.get("avg_time") or 0.0, 2)
            except Exception as e:
                logger.debug("Aggregation query error: %s", e)

        blocking_pct = round((total_throttled / max(total_reqs, 1)) * 100, 2)
        error_pct = round((total_errors / max(total_reqs, 1)) * 100, 2)

        # Recent events
        recent_events = []
        if db is not None:
            try:
                cursor = db.rate_limit_events.find().sort("timestamp", -1).limit(10)
                docs = await cursor.to_list(10)
                for d in docs:
                    d["id"] = str(d.pop("_id", ""))
                    if d.get("timestamp") and hasattr(d["timestamp"], "isoformat"):
                        d["timestamp"] = d["timestamp"].isoformat()
                    if d.get("cooldown_until") and hasattr(d["cooldown_until"], "isoformat"):
                        d["cooldown_until"] = d["cooldown_until"].isoformat()
                    recent_events.append(d)
            except Exception:
                pass

        return {
            "total_requests": total_reqs,
            "successful_requests": total_succ,
            "throttled_429_count": total_throttled,
            "forbidden_403_count": total_forbidden,
            "other_error_count": total_errors,
            "error_percentage": error_pct,
            "blocking_percentage": blocking_pct,
            "average_response_time_ms": avg_resp_time,
            "active_monitored_domains": monitored_domains,
            "paused_domains": paused_domains,
            "recent_events": recent_events,
        }

    async def get_domain_breakdown(self, search: Optional[str] = None, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists domain rate profiles persisted in MongoDB.
        """
        db = self.database
        if db is None:
            return []

        query: Dict[str, Any] = {}
        if search:
            query["domain"] = {"$regex": search, "$options": "i"}
        if status_filter:
            query["status"] = status_filter

        cursor = db.domain_rate_profiles.find(query).sort("total_requests", -1).limit(100)
        docs = await cursor.to_list(100)

        res = []
        for d in docs:
            d["id"] = str(d.pop("_id", ""))
            if d.get("last_observed_at") and hasattr(d["last_observed_at"], "isoformat"):
                d["last_observed_at"] = d["last_observed_at"].isoformat()
            if d.get("cooldown_until") and hasattr(d["cooldown_until"], "isoformat"):
                d["cooldown_until"] = d["cooldown_until"].isoformat()
            if d.get("updated_at") and hasattr(d["updated_at"], "isoformat"):
                d["updated_at"] = d["updated_at"].isoformat()
            res.append(d)
        return res

    # --- Mode A: Pause / Resume / Reset Controls ---
    async def pause_domain(self, domain_name: str, reason: str = "Administrative manual hold") -> Dict[str, Any]:
        domain = self._get_domain(domain_name)
        now = datetime.now(timezone.utc)
        db = self.database
        if db is not None:
            await db.domain_rate_profiles.update_one(
                {"domain": domain},
                {"$set": {"is_paused": True, "status": "paused", "updated_at": now}},
                upsert=True,
            )
            await db.rate_limit_events.insert_one({
                "domain": domain,
                "event_type": "domain_paused",
                "severity": "info",
                "reason": reason,
                "timestamp": now,
            })
        return {"domain": domain, "status": "paused", "is_paused": True}

    async def resume_domain(self, domain_name: str) -> Dict[str, Any]:
        domain = self._get_domain(domain_name)
        now = datetime.now(timezone.utc)
        db = self.database
        if db is not None:
            await db.domain_rate_profiles.update_one(
                {"domain": domain},
                {"$set": {"is_paused": False, "status": "normal", "updated_at": now}},
            )
            await db.rate_limit_events.insert_one({
                "domain": domain,
                "event_type": "domain_resumed",
                "severity": "info",
                "reason": "Administrative manual resume",
                "timestamp": now,
            })
        return {"domain": domain, "status": "normal", "is_paused": False}

    async def reset_domain_profile(self, domain_name: str) -> Dict[str, Any]:
        domain = self._get_domain(domain_name)
        now = datetime.now(timezone.utc)
        db = self.database
        if db is not None:
            await db.domain_rate_profiles.update_one(
                {"domain": domain},
                {
                    "$set": {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "blocked_requests": 0,
                        "blocking_percentage": 0.0,
                        "average_response_time": 0.0,
                        "confidence": "INSUFFICIENT DATA",
                        "status": "normal",
                        "active_interval_ms": 1000.0,
                        "estimated_interval_ms": 1000.0,
                        "active_concurrency": 3,
                        "is_paused": False,
                        "updated_at": now,
                    }
                },
            )
        return {"domain": domain, "message": "Domain metrics reset successfully"}

    async def reset_all(self) -> None:
        db = self.database
        if db is not None:
            await db.rate_limit_request_logs.delete_many({})
            await db.rate_limit_metrics.delete_many({})
            await db.domain_rate_profiles.delete_many({})
            await db.rate_limit_events.delete_many({})

    # --- Request Logs & CSV Export ---
    async def get_request_logs(
        self,
        domain: Optional[str] = None,
        classification: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        db = self.database
        if db is None:
            return [], 0
        query: Dict[str, Any] = {}
        if domain:
            query["domain"] = domain
        if classification:
            query["classification"] = classification

        total = await db.rate_limit_request_logs.count_documents(query)
        cursor = db.rate_limit_request_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(limit)
        cursor = self.db.rate_limit_request_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(limit)

        items = []
        for d in docs:
            d["id"] = str(d.pop("_id", ""))
            if d.get("timestamp") and hasattr(d["timestamp"], "isoformat"):
                d["timestamp"] = d["timestamp"].isoformat()
            items.append(d)
        return items, total

    async def export_logs_csv(self, domain: Optional[str] = None) -> str:
        logs, _ = await self.get_request_logs(domain=domain, limit=1000)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Domain", "Endpoint", "Method", "Status Code", "Classification", "Latency (ms)", "Retry After", "Error Reason"])
        for l in logs:
            writer.writerow([
                l.get("timestamp"),
                l.get("domain"),
                l.get("endpoint"),
                l.get("method"),
                l.get("status_code"),
                l.get("classification"),
                l.get("response_time_ms"),
                l.get("retry_after"),
                l.get("error_reason"),
            ])
        return output.getvalue()

    # --- Mode B: GitHub API Provider Integration ---
    async def refresh_github_quota(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Polls GitHub REST API GET /rate_limit, tracks primary limits and dynamic resource buckets.
        Masks the token securely.
        """
        now = datetime.now(timezone.utc)
        stored_token = token
        db = self.database
        if not stored_token and db is not None:
            stored = await db.api_rate_limit_profiles.find_one({"provider": "github"})
            if stored and stored.get("token"):
                stored_token = stored["token"]

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "CandidDigital-RateLimitChecker/1.0",
        }
        if stored_token:
            headers["Authorization"] = f"Bearer {stored_token}"

        auth_status = "authenticated" if stored_token else "unauthenticated"
        resources_dict = {}

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get("https://api.github.com/rate_limit", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    res_raw = data.get("resources", {})
                    for r_name, r_data in res_raw.items():
                        limit = r_data.get("limit", 0)
                        remaining = r_data.get("remaining", 0)
                        used = r_data.get("used", limit - remaining)
                        reset_ts = r_data.get("reset", 0)
                        reset_dt = datetime.fromtimestamp(reset_ts, timezone.utc) if reset_ts else now
                        utilization = round((used / max(limit, 1)) * 100, 1)

                        resources_dict[r_name] = {
                            "resource": r_name,
                            "limit": limit,
                            "remaining": remaining,
                            "used": used,
                            "reset_at": reset_dt.isoformat(),
                            "utilization_pct": utilization,
                        }
                elif resp.status_code == 401:
                    auth_status = "expired"
                else:
                    auth_status = f"error_{resp.status_code}"
        except Exception as e:
            logger.warning("GitHub rate limit request failed: %s", e)
            auth_status = "unreachable"

        masked = f"{stored_token[:4]}...{stored_token[-4:]}" if stored_token and len(stored_token) > 8 else None

        profile_doc = {
            "provider": "github",
            "auth_status": auth_status,
            "is_configured": bool(stored_token),
            "token_masked": masked,
            "last_refreshed_at": now.isoformat(),
            "resources": resources_dict,
        }

        if db is not None:
            update_payload = dict(profile_doc)
            if stored_token:
                update_payload["token"] = stored_token
            await db.api_rate_limit_profiles.update_one(
                {"provider": "github"},
                {"$set": update_payload},
                upsert=True,
            )

        return profile_doc

    async def get_github_status(self) -> Dict[str, Any]:
        db = self.database
        if db is not None:
            profile = await db.api_rate_limit_profiles.find_one({"provider": "github"})
            if profile:
                profile.pop("token", None)  # Never expose secret token
                profile["id"] = str(profile.pop("_id", ""))
                return profile
        return await self.refresh_github_quota()

    async def configure_github_token(self, token: str) -> Dict[str, Any]:
        return await self.refresh_github_quota(token=token.strip())


# Global singleton instance
rate_limit_service = RateLimitService()
