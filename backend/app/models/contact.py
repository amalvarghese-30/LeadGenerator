from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ContactDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None  # reference to companies collection
    company_name: Optional[str] = None  # denormalized for performance
    professional_urls: Dict[str, str] = Field(default_factory=dict)  # {linkedin, twitter, github, website}
    business_contacts: Dict[str, str] = Field(default_factory=dict)  # {email, phone, work_email, mobile}
    contact_verification_status: str = "unverified"  # unverified|pending|verified|bounced|invalid
    source_references: List[Dict] = Field(default_factory=list)  # [{source, url, found_at}]
    dedup_key: Optional[str] = None
    is_suppressed: bool = False
    do_not_contact: bool = False
    suppression_reason: Optional[str] = None
    gdpr_consented: bool = False
    last_contacted_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
