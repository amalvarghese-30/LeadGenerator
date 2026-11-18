from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ContactChannel(BaseModel):
    """
    Individual verified public business contact channel (email, phone, form, social).
    Retains full source provenance and multi-step verification status.
    """
    type: str  # email | phone | contact_form | social | website
    scope: str = "unclassified"  # person_direct_work | company_generic | company_switchboard | department | media_enquiry | sales_enquiry | unclassified
    value: str
    source_url: Optional[str] = None
    source_type: Optional[str] = "webpage"  # webpage | json_ld | mailto | tel | directory | ddgs_search | manual
    evidence_quote: Optional[str] = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_checked_at: Optional[datetime] = None
    syntax_valid: bool = True
    mx_record_found: Optional[bool] = None
    domain_valid: Optional[bool] = None
    source_verified: bool = False
    human_reviewed: bool = False
    confidence: float = 0.5
    verification_status: str = "discovered"  # not_found | discovered | published | format_checked | source_verified | human_reviewed | rejected
    notes: Optional[str] = None

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ContactDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None  # reference to companies collection
    company_name: Optional[str] = None  # denormalized for performance
    associated_companies: List[Dict[str, Any]] = Field(default_factory=list)  # multiple company associations [{company_id, company_name, designation}]
    
    # Backwards-compatible dictionaries
    professional_urls: Dict[str, str] = Field(default_factory=dict)  # {linkedin, twitter, instagram, website}
    business_contacts: Dict[str, str] = Field(default_factory=dict)  # {email, phone, work_email, mobile}
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    # Structured multi-channel list with full provenance
    contact_channels: List[ContactChannel] = Field(default_factory=list)

    # Verification and enrichment lifecycle
    contact_verification_status: str = "discovered"  # discovered | source_reviewed | company_verified | contact_source_verified | human_approved | rejected
    enrichment_status: str = "not_started"  # not_started | in_progress | enriched | partially_enriched | no_public_contacts_found | failed
    last_enriched_at: Optional[datetime] = None
    enrichment_attempts: int = 0
    enrichment_errors: List[str] = Field(default_factory=list)
    identity_profile: Optional[Dict[str, Any]] = None

    # Evidence & governance
    source_references: List[Any] = Field(default_factory=list)  # reference IDs or reference objects
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
