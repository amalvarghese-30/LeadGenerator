from typing import Dict, List, Optional
from pydantic import BaseModel


class LeadCreate(BaseModel):
    contact_id: str
    company_id: Optional[str] = None
    lead_source: str = "manual"
    provider_id: Optional[str] = None
    owner: Optional[str] = None
    lead_priority: str = "medium"
    tags: List[str] = []
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    company_id: Optional[str] = None
    lead_priority: Optional[str] = None
    owner: Optional[str] = None
    outreach_eligible: Optional[bool] = None
    next_follow_up: Optional[str] = None
    qualification_status: Optional[str] = None
    disqualification_reason: Optional[str] = None
    custom_fields: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class LeadStatusUpdate(BaseModel):
    crm_stage: str
    reason: Optional[str] = None
    notes: Optional[str] = None


class LeadQualifyRequest(BaseModel):
    qualification_status: str  # qualified|disqualified|in_progress
    disqualification_reason: Optional[str] = None
    notes: Optional[str] = None


class LeadResponse(BaseModel):
    id: str
    contact_id: str
    company_id: Optional[str] = None
    lead_score: float
    lead_priority: str
    crm_stage: str
    owner: Optional[str] = None
    lead_source: str
    provider_id: Optional[str] = None
    qualification_status: str
    outreach_eligible: bool
    last_activity: Optional[str] = None
    next_follow_up: Optional[str] = None
    follow_up_count: int
    score_breakdown: Dict[str, float] = {}
    disqualification_reason: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
