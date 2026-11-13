from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuditLogDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str  # create|read|update|delete|login|logout|export|import|status_change
    resource_type: str  # user|provider|lead|contact|company|activity|crawl_job|...
    resource_id: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None  # {field: {old: ..., new: ...}}
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    response_status: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
