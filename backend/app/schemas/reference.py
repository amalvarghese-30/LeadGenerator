from typing import Optional
from pydantic import BaseModel, Field


class ReferenceCreate(BaseModel):
    provider_id: str
    company_id: Optional[str] = None
    person_name: Optional[str] = None
    designation: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    client_name: Optional[str] = None
    client_website: Optional[str] = None
    client_domain: Optional[str] = None
    client_industry: Optional[str] = None
    client_country: Optional[str] = None
    reference_type: str = "client_portfolio_reference"
    relationship_type: Optional[str] = None
    source_url: Optional[str] = None
    evidence_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    evidence_quote: Optional[str] = None
    confidence: float = 0.8
    confidence_score: float = 0.8
    verification_status: str = "pending_review"
    notes: Optional[str] = None


class ReferenceVerify(BaseModel):
    action: str  # verify|reject
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class ReferenceResponse(BaseModel):
    id: str
    provider_id: str
    company_id: Optional[str] = None
    person_name: Optional[str] = None
    designation: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    client_name: Optional[str] = None
    client_website: Optional[str] = None
    client_domain: Optional[str] = None
    client_industry: Optional[str] = None
    client_country: Optional[str] = None
    reference_type: str = "client_portfolio_reference"
    relationship_type: Optional[str] = None
    source_url: Optional[str] = None
    evidence_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    evidence_quote: Optional[str] = None
    confidence: float = 0.8
    confidence_score: float = 0.8
    verification_status: str
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
