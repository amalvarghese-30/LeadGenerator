from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class ProviderClientReferenceDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    provider_id: str
    client_name: str
    client_website: Optional[str] = None
    client_domain: Optional[str] = None
    client_industry: Optional[str] = None
    client_country: Optional[str] = None
    reference_type: str = "inferred"  # inferred|confirmed|case_study|testimonial|logo
    evidence_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    confidence_score: float = 0.5  # 0.0 - 1.0
    verification_status: str = "unverified"  # unverified|verified|rejected
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
