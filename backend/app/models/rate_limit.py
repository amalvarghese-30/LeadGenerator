from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RateLimitRequestLog(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    worker_id: Optional[str] = None
    domain: str
    endpoint: Optional[str] = None
    method: str = "GET"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status_code: Optional[int] = None
    classification: str = "UNKNOWN"
    response_time_ms: float = 0.0
    request_interval_ms: Optional[float] = None
    retry_count: int = 0
    relevant_headers: Dict[str, str] = Field(default_factory=dict)
    concurrency: int = 1
    policy_scope: str = "domain"
    provider: Optional[str] = None
    error_reason: Optional[str] = None

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class DomainRateProfile(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    domain: str
    provider_type: str = "website"
    policy_scope: str = "domain"
    observed_limit: Optional[str] = None
    estimated_interval_ms: float = 1000.0
    active_interval_ms: float = 1000.0
    active_concurrency: int = 3
    successful_requests: int = 0
    blocked_requests: int = 0
    total_requests: int = 0
    blocking_percentage: float = 0.0
    average_response_time: float = 0.0
    confidence: str = "INSUFFICIENT DATA"  # INSUFFICIENT DATA | LOW | MEDIUM | HIGH
    status: str = "normal"  # normal | cautious | paused | attention_required
    cooldown_until: Optional[datetime] = None
    is_paused: bool = False
    last_observed_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class RateLimitEvent(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    domain: str
    event_type: str  # rate_limited | domain_paused | domain_resumed | cooldown_started | cooldown_ended | retry_exhausted
    severity: str = "info"  # info | warning | critical
    reason: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ResourceQuota(BaseModel):
    resource: str
    limit: int
    remaining: int
    used: int
    reset_at: datetime
    utilization_pct: float = 0.0


class ApiRateLimitProfile(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    provider: str = "github"
    auth_status: str = "unauthenticated"  # authenticated | unauthenticated | expired
    is_configured: bool = False
    token_masked: Optional[str] = None
    last_refreshed_at: Optional[datetime] = None
    resources: Dict[str, ResourceQuota] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class RateLimitSettings(BaseModel):
    rate_limit_enabled: bool = True
    auto_control: bool = True
    default_interval_ms: int = 1500
    max_concurrency: int = 5
    initial_backoff_sec: float = 2.0
    max_backoff_sec: float = 60.0
    max_retries: int = 3
    log_retention_days: int = 30
    github_enabled: bool = False

    model_config = {"populate_by_name": True}


# Backward-compatible model
class RateLimitMetric(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    domain: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    is_throttled: bool = False
    retry_after: Optional[int] = None
    rate_limit_headers: Dict[str, str] = Field(default_factory=dict)
    error_type: Optional[str] = None
    action_taken: Optional[str] = None

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
