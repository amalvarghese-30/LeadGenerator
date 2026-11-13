from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


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
