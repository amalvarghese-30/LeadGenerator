"""
Rate Limit Checker and Adaptive Scheduling Engine.
- Tracks per-domain request metrics, 429s, 403s, errors, response times, Retry-After headers.
- Emits safe crawl delays and concurrency recommendations using exponential backoff with jitter.
- Persists metrics to MongoDB `rate_limit_metrics`.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainState:
    def __init__(self, domain: str):
        self.domain = domain
        self.requests_count = 0
        self.success_count = 0
        self.throttled_count = 0
        self.forbidden_count = 0
        self.error_count = 0
        self.total_response_time_ms = 0.0
        self.last_status_code: Optional[int] = None
        self.last_throttled_at: Optional[datetime] = None
        self.last_retry_after: Optional[int] = None
        self.backoff_level: int = 0
        self.current_delay_seconds: float = 1.0
        self.current_concurrency: int = 3
        self.active_requests: int = 0
        self.last_request_at: Optional[datetime] = None


class RateLimitService:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self._domains: Dict[str, DomainState] = {}
        self._lock = asyncio.Lock()

    def _get_domain(self, url_or_domain: str) -> str:
        if "://" in url_or_domain:
            parsed = urlparse(url_or_domain)
            return (parsed.netloc or "").lower().split(":")[0]
        return url_or_domain.lower().split(":")[0]

    async def get_or_create_domain_state(self, domain_name: str) -> DomainState:
        domain = self._get_domain(domain_name)
        async with self._lock:
            if domain not in self._domains:
                self._domains[domain] = DomainState(domain)
            return self._domains[domain]

    async def record_request_metric(
        self,
        url_or_domain: str,
        status_code: Optional[int],
        response_time_ms: float,
        headers: Optional[Dict[str, str]] = None,
        error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record the result of an HTTP request, updating in-memory domain state and MongoDB log.
        """
        domain = self._get_domain(url_or_domain)
        state = await self.get_or_create_domain_state(domain)
        now = datetime.now(timezone.utc)
        headers = headers or {}

        # Parse Retry-After if present
        retry_after_val: Optional[int] = None
        for k, v in headers.items():
            if k.lower() == "retry-after":
                try:
                    retry_after_val = int(v)
                except ValueError:
                    pass

        # Determine rate limiting or error
        is_429 = status_code == 429
        is_403 = status_code == 403
        is_success = status_code is not None and 200 <= status_code < 400
        is_err = not is_success

        state.requests_count += 1
        state.total_response_time_ms += response_time_ms
        state.last_status_code = status_code
        state.last_request_at = now

        action_taken = "normal"
        if is_success:
            state.success_count += 1
            # Gradually heal backoff if successful
            if state.backoff_level > 0 and random.random() < 0.2:
                state.backoff_level = max(0, state.backoff_level - 1)
                state.current_delay_seconds = max(1.0, state.current_delay_seconds * 0.8)
                state.current_concurrency = min(5, state.current_concurrency + 1)
        elif is_429 or is_403:
            if is_429:
                state.throttled_count += 1
            else:
                state.forbidden_count += 1
            state.last_throttled_at = now
            state.last_retry_after = retry_after_val

            # Adaptive Backoff calculation: exponential backoff with jitter
            state.backoff_level += 1
            jitter = random.uniform(0.2, 0.8)
            if retry_after_val:
                state.current_delay_seconds = float(retry_after_val) + jitter
                action_taken = f"honor_retry_after_{retry_after_val}s"
            else:
                # 2^(backoff) + jitter
                state.current_delay_seconds = min(30.0, (2.0 ** min(state.backoff_level, 4)) + jitter)
                action_taken = f"exponential_backoff_{state.current_delay_seconds:.1f}s"

            # Reduce concurrency down to 1
            state.current_concurrency = max(1, state.current_concurrency - 1)
        else:
            state.error_count += 1
            if state.error_count % 3 == 0:
                state.current_delay_seconds = min(15.0, state.current_delay_seconds * 1.5)
                state.current_concurrency = max(1, state.current_concurrency - 1)
                action_taken = "degraded_concurrency_and_delay"

        # Rate limit headers subset
        rl_headers = {
            k: v for k, v in headers.items()
            if any(h in k.lower() for h in ["ratelimit", "retry-after", "cf-ray", "server"])
        }

        doc = {
            "domain": domain,
            "timestamp": now,
            "status_code": status_code,
            "response_time_ms": round(response_time_ms, 2),
            "is_throttled": is_429 or is_403,
            "retry_after": retry_after_val,
            "rate_limit_headers": rl_headers,
            "error_type": error_type,
            "action_taken": action_taken,
        }

        if self.db is not None:
            try:
                await self.db.rate_limit_metrics.insert_one(dict(doc))
            except Exception as e:
                logger.debug("Failed to persist rate limit metric: %s", e)

        return doc

    async def get_domain_policy(self, url_or_domain: str) -> Dict[str, Any]:
        """
        Returns safe scheduling recommendations: recommended delay and concurrency.
        """
        domain = self._get_domain(url_or_domain)
        state = await self.get_or_create_domain_state(domain)
        return {
            "domain": domain,
            "recommended_delay_seconds": round(state.current_delay_seconds, 2),
            "max_concurrency": state.current_concurrency,
            "backoff_level": state.backoff_level,
            "last_throttled_at": state.last_throttled_at.isoformat() if state.last_throttled_at else None,
            "last_retry_after": state.last_retry_after,
        }

    async def get_summary_metrics(self) -> Dict[str, Any]:
        """
        Returns global overview statistics across all monitored domains.
        """
        total_reqs = sum(s.requests_count for s in self._domains.values())
        total_succ = sum(s.success_count for s in self._domains.values())
        total_throttled = sum(s.throttled_count for s in self._domains.values())
        total_forbidden = sum(s.forbidden_count for s in self._domains.values())
        total_errors = sum(s.error_count for s in self._domains.values())
        total_time = sum(s.total_response_time_ms for s in self._domains.values())
        avg_resp_time = round(total_time / max(total_reqs, 1), 2)
        err_pct = round(((total_throttled + total_forbidden + total_errors) / max(total_reqs, 1)) * 100, 2)

        # Recent events from DB if available
        recent_events = []
        if self.db is not None:
            try:
                cursor = self.db.rate_limit_metrics.find().sort("timestamp", -1).limit(20)
                docs = await cursor.to_list(length=20)
                for d in docs:
                    if "_id" in d:
                        d["id"] = str(d.pop("_id"))
                    if d.get("timestamp") and hasattr(d["timestamp"], "isoformat"):
                        d["timestamp"] = d["timestamp"].isoformat()
                    recent_events.append(d)
            except Exception as e:
                logger.debug("Error fetching recent rate limit events: %s", e)

        return {
            "total_requests": total_reqs,
            "successful_requests": total_succ,
            "throttled_429_count": total_throttled,
            "forbidden_403_count": total_forbidden,
            "other_error_count": total_errors,
            "error_percentage": err_pct,
            "average_response_time_ms": avg_resp_time,
            "active_monitored_domains": len(self._domains),
            "recent_events": recent_events,
        }

    async def get_domain_breakdown(self) -> List[Dict[str, Any]]:
        """
        Returns list of per-domain performance metrics.
        """
        res = []
        for domain, s in self._domains.items():
            avg_ms = round(s.total_response_time_ms / max(s.requests_count, 1), 2)
            err_pct = round(((s.throttled_count + s.forbidden_count + s.error_count) / max(s.requests_count, 1)) * 100, 2)
            res.append({
                "domain": domain,
                "requests": s.requests_count,
                "success": s.success_count,
                "throttled_429": s.throttled_count,
                "forbidden_403": s.forbidden_count,
                "errors": s.error_count,
                "error_rate_pct": err_pct,
                "avg_response_time_ms": avg_ms,
                "configured_delay_seconds": round(s.current_delay_seconds, 2),
                "concurrency": s.current_concurrency,
                "last_throttled_at": s.last_throttled_at.isoformat() if s.last_throttled_at else None,
                "last_retry_after": s.last_retry_after,
            })
        return sorted(res, key=lambda x: x["requests"], reverse=True)

    async def reset(self) -> None:
        async with self._lock:
            self._domains.clear()
        if self.db is not None:
            try:
                await self.db.rate_limit_metrics.delete_many({})
            except Exception:
                pass


# Global singleton instance
rate_limit_service = RateLimitService()
