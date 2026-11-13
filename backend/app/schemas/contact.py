from typing import Dict, List, Optional
from pydantic import BaseModel


class ContactCreate(BaseModel):
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    professional_urls: Dict[str, str] = {}
    business_contacts: Dict[str, str] = {}
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
    professional_urls: Optional[Dict[str, str]] = None
    business_contacts: Optional[Dict[str, str]] = None
    contact_verification_status: Optional[str] = None
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
    professional_urls: Dict[str, str] = {}
    business_contacts: Dict[str, str] = {}
    contact_verification_status: str
    is_suppressed: bool
    do_not_contact: bool
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
