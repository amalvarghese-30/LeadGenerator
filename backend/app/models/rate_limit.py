from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


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
