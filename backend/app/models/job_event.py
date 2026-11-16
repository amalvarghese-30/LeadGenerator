from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class JobEventDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    job_id: str
    event_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: str
    severity: str = "info"  # info, warning, error, success
    event_type: str
    message: str
    url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
