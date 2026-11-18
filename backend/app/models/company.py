from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContactChannel(BaseModel):
    type: str  # email | phone | contact_form | social
    scope: str = "company_generic"  # company_generic | company_department | person_direct_work | unclassified
    value: str
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    evidence_quote: Optional[str] = None
    syntax_valid: bool = True
    source_verified: bool = False
    verification_status: str = "published"  # published | format_checked | verified | unverified
    confidence: float = 0.9
    collected_at: Optional[str] = None


class CompanyDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    linkedin_url: Optional[str] = None
    employee_count: Optional[str] = None
    revenue_range: Optional[str] = None
    public_contact: Dict[str, str] = Field(default_factory=dict)  # {email, phone, address}
    public_contact_channels: List[Dict[str, Any]] = Field(default_factory=list)
    social_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    enrichment_status: str = "pending"  # pending | enriching | enriched | partial | no_website | failed
    enrichment_attempts: int = 0
    last_enriched_at: Optional[datetime] = None
    source_references: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    verification_status: str = "unverified"  # unverified|pending|verified|rejected
    dedup_key: Optional[str] = None  # normalized key for deduplication
    source: str = "manual"
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
