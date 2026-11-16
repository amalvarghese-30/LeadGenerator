from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProfileCandidateDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    full_name: str
    company_name: Optional[str] = None
    designation: Optional[str] = None
    location: Optional[str] = None
    confidence_score: float = 0.0
    confidence_level: str = "medium"  # low, medium, high
    platform_profiles: Dict[str, str] = Field(default_factory=dict)  # linkedin, twitter, github, etc.
    professional_biography: Optional[str] = None
    official_website: Optional[str] = None
    contact_channels: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    verification_status: str = "pending_review"  # detected, pending_review, confirmed, rejected
    saved_contact_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
