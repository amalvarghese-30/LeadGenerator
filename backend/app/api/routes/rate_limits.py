"""
Rate Limit Checker API Router.
Complete full-featured endpoints for:
- Mode A: General Website Rate Limit Monitoring & Adaptive Scheduling
- Mode B: GitHub API Provider Quota & Secondary Rate Limits
- Incident logging, domain pause/resume, and CSV export.
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.services.rate_limit_service import rate_limit_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rate-limits", tags=["Rate Limit Checker"])


class LogMetricRequest(BaseModel):
    domain: str
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    headers: Dict[str, str] = Field(default_factory=dict)
    error_type: Optional[str] = None
    endpoint: Optional[str] = None
    method: str = "GET"


class PauseDomainRequest(BaseModel):
    reason: Optional[str] = "Administrative manual hold"


class GitHubConfigRequest(BaseModel):
    token: str = Field(..., min_length=1)


@router.get("/overview")
@router.get("/metrics")
async def get_rate_limit_metrics(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.get_summary_metrics()


@router.get("/domains")
async def get_domain_rate_limits(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.get_domain_breakdown(search=search, status_filter=status)


@router.get("/domains/{domain:path}")
async def get_single_domain_profile(
    domain: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.get_domain_policy(domain)


@router.post("/domains/{domain:path}/pause")
async def pause_domain_route(
    domain: str,
    data: Optional[PauseDomainRequest] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    reason = data.reason if data else "Administrative manual hold"
    return await rate_limit_service.pause_domain(domain, reason=reason)


@router.post("/domains/{domain:path}/resume")
async def resume_domain_route(
    domain: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.resume_domain(domain)


@router.post("/domains/{domain:path}/reset-profile")
async def reset_domain_profile_route(
    domain: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.reset_domain_profile(domain)


@router.get("/policy/{domain:path}")
async def get_domain_policy_recommendation(
    domain: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.get_domain_policy(domain)


@router.get("/requests")
async def get_request_logs_route(
    domain: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    page: int = Query(1, ge=1),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    skip = (page - 1) * limit
    items, total = await rate_limit_service.get_request_logs(
        domain=domain,
        classification=classification,
        limit=limit,
        skip=skip,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/events")
async def get_incidents_route(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    cursor = db.rate_limit_events.find().sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(limit)
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
        if d.get("timestamp") and hasattr(d["timestamp"], "isoformat"):
            d["timestamp"] = d["timestamp"].isoformat()
        if d.get("cooldown_until") and hasattr(d["cooldown_until"], "isoformat"):
            d["cooldown_until"] = d["cooldown_until"].isoformat()
    return docs


@router.get("/export/csv")
async def export_rate_limit_csv(
    domain: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    csv_content = await rate_limit_service.export_logs_csv(domain=domain)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rate_limit_logs_{domain or 'all'}.csv"},
    )


# --- Mode B: API Providers ---
@router.get("/providers")
async def list_providers_route(
    _user: dict = Depends(get_current_user),
):
    return [
        {
            "id": "github",
            "name": "GitHub REST API",
            "description": "Primary rate limits, resource quotas (core, search, graphql), and secondary limit detection",
            "is_supported": True,
        }
    ]


@router.get("/providers/github/status")
async def get_github_quota_status(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.get_github_status()


@router.post("/providers/github/refresh")
async def refresh_github_quota_route(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.refresh_github_quota()


@router.post("/providers/github/configure")
async def configure_github_token_route(
    data: GitHubConfigRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.configure_github_token(data.token)


@router.post("/log")
async def log_rate_limit_metric(
    data: LogMetricRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.record_request_metric(
        url_or_domain=data.domain,
        status_code=data.status_code,
        response_time_ms=data.response_time_ms,
        headers=data.headers,
        error_type=data.error_type,
        endpoint=data.endpoint,
        method=data.method,
    )


@router.post("/reset")
async def reset_rate_limit_metrics(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    await rate_limit_service.reset_all()
    return {"message": "Rate limit metrics and logs reset successfully"}
