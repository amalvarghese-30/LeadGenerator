from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

ACTIVITY_TYPES = [
    "note",
    "call",
    "email_recorded",
    "meeting",
    "follow_up",
    "verification",
    "status_change",
]


class ActivityDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    activity_type: str  # note|call|email_recorded|meeting|follow_up|verification|status_change
    title: Optional[str] = None
    description: Optional[str] = None
    # Relations (at least one should be set)
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    provider_id: Optional[str] = None
    # Status change metadata
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    # Scheduled / duration
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None  # positive|neutral|negative
    # Attachments / metadata
    metadata: Dict = Field(default_factory=dict)
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
