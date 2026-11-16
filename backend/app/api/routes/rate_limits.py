"""
Rate Limit Checker API Router.
- Get global metrics summary
- Get per-domain telemetry & stats
- Get domain scheduling policy recommendation
- Record/log manual test metric
- Reset metrics
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
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


@router.get("/metrics")
async def get_rate_limit_metrics(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    return await rate_limit_service.get_summary_metrics()


@router.get("/domains")
async def get_domain_rate_limits(
    _user: dict = Depends(get_current_user),
):
    return await rate_limit_service.get_domain_breakdown()


@router.get("/policy/{domain:path}")
async def get_domain_policy_recommendation(
    domain: str,
    _user: dict = Depends(get_current_user),
):
    return await rate_limit_service.get_domain_policy(domain)


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
    )


@router.post("/reset")
async def reset_rate_limit_metrics(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    rate_limit_service.db = db
    await rate_limit_service.reset()
    return {"message": "Rate limit metrics reset successfully"}
