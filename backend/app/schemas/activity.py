from typing import Dict, Optional
from pydantic import BaseModel


class ActivityCreate(BaseModel):
    activity_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    provider_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None
    metadata: Dict = {}


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None
    metadata: Optional[Dict] = None


class ActivityResponse(BaseModel):
    id: str
    activity_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    provider_id: Optional[str] = None
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    scheduled_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None
    metadata: Dict = {}
    created_by: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}
