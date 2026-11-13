from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ContactChannelSchema(BaseModel):
    type: str  # email | phone | contact_form | social | website
    scope: str = "unclassified"
    value: str
    source_url: Optional[str] = None
    source_type: Optional[str] = "webpage"
    evidence_quote: Optional[str] = None
    collected_at: Optional[Any] = None
    last_checked_at: Optional[Any] = None
    syntax_valid: bool = True
    mx_record_found: Optional[bool] = None
    domain_valid: Optional[bool] = None
    source_verified: bool = False
    human_reviewed: bool = False
    confidence: float = 0.5
    verification_status: str = "discovered"
    notes: Optional[str] = None


class ContactCreate(BaseModel):
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    professional_urls: Dict[str, str] = {}
    business_contacts: Dict[str, str] = {}
    contact_channels: List[ContactChannelSchema] = []
    tags: List[str] = []
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    professional_urls: Optional[Dict[str, str]] = None
    business_contacts: Optional[Dict[str, str]] = None
    contact_channels: Optional[List[ContactChannelSchema]] = None
    contact_verification_status: Optional[str] = None
    enrichment_status: Optional[str] = None
    is_suppressed: Optional[bool] = None
    do_not_contact: Optional[bool] = None
    suppression_reason: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    professional_urls: Dict[str, str] = {}
    business_contacts: Dict[str, str] = {}
    contact_channels: List[ContactChannelSchema] = []
    contact_verification_status: str
    enrichment_status: str = "not_started"
    last_enriched_at: Optional[Any] = None
    enrichment_attempts: int = 0
    enrichment_errors: List[str] = []
    is_suppressed: bool = False
    do_not_contact: bool = False
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
