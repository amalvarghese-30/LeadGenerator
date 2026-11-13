from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

CRM_STAGES = [
    "discovered",
    "pending_verification",
    "verified",
    "qualified",
    "ready_for_outreach_review",
    "contacted",
    "replied",
    "interested",
    "converted",
    "closed",
    "disqualified",
    "do_not_contact",
]


class LeadDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    contact_id: str
    company_id: Optional[str] = None
    # Score & priority
    lead_score: float = 0.0  # 0-100
    lead_priority: str = "medium"  # low|medium|high|urgent
    # CRM pipeline
    crm_stage: str = "discovered"
    previous_stage: Optional[str] = None
    stage_changed_at: Optional[datetime] = None
    # Ownership
    owner: Optional[str] = None  # user_id of assigned SDR/AE
    # Source
    lead_source: str = "manual"  # manual|discovery|import|referral
    provider_id: Optional[str] = None  # which provider generated this lead
    # Qualification
    qualification_status: str = "unqualified"  # unqualified|in_progress|qualified|disqualified
    outreach_eligible: bool = False
    # Follow-up
    last_activity: Optional[datetime] = None
    next_follow_up: Optional[datetime] = None
    follow_up_count: int = 0
    # Scoring breakdown
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    # Disqualification
    disqualification_reason: Optional[str] = None
    # Custom fields
    custom_fields: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
