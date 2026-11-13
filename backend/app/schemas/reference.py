from typing import Optional
from pydantic import BaseModel


class ReferenceCreate(BaseModel):
    provider_id: str
    client_name: str
    client_website: Optional[str] = None
    client_domain: Optional[str] = None
    client_industry: Optional[str] = None
    client_country: Optional[str] = None
    reference_type: str = "inferred"
    evidence_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    confidence_score: float = 0.5
    notes: Optional[str] = None


class ReferenceVerify(BaseModel):
    action: str  # verify|reject
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class ReferenceResponse(BaseModel):
    id: str
    provider_id: str
    client_name: str
    client_website: Optional[str] = None
    client_domain: Optional[str] = None
    client_industry: Optional[str] = None
    client_country: Optional[str] = None
    reference_type: str
    evidence_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    confidence_score: float
    verification_status: str
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
