from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ProviderClientReferenceDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    provider_id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    client_name: Optional[str] = None
    client_website: Optional[str] = None
    client_domain: Optional[str] = None
    client_industry: Optional[str] = None
    client_country: Optional[str] = None
    reference_type: str = "client_portfolio_reference"  # inferred|confirmed|case_study|testimonial|logo|client_portfolio_reference
    relationship_type: Optional[str] = None
    source_url: Optional[str] = None
    evidence_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    evidence_quote: Optional[str] = None
    confidence: float = 0.8
    confidence_score: float = 0.8
    verification_status: str = "pending_review"  # unverified|verified|rejected|pending_review
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
