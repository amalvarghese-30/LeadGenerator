from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    aliases: List[str] = []
    linkedin_url: Optional[str] = None
    employee_count: Optional[str] = None
    revenue_range: Optional[str] = None
    public_contact: Dict[str, str] = {}
    public_contact_channels: List[Dict[str, Any]] = []
    social_profiles: List[Dict[str, Any]] = []
    associated_people: List[Dict[str, Any]] = []
    description: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    aliases: Optional[List[str]] = None
    linkedin_url: Optional[str] = None
    employee_count: Optional[str] = None
    revenue_range: Optional[str] = None
    public_contact: Optional[Dict[str, str]] = None
    public_contact_channels: Optional[List[Dict[str, Any]]] = None
    social_profiles: Optional[List[Dict[str, Any]]] = None
    associated_people: Optional[List[Dict[str, Any]]] = None
    enrichment_status: Optional[str] = None
    description: Optional[str] = None
    verification_status: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    aliases: List[str] = []
    linkedin_url: Optional[str] = None
    employee_count: Optional[str] = None
    revenue_range: Optional[str] = None
    public_contact: Dict[str, str] = {}
    public_contact_channels: List[Dict[str, Any]] = []
    social_profiles: List[Dict[str, Any]] = []
    associated_people: List[Dict[str, Any]] = []
    enrichment_status: str = "pending"
    enrichment_attempts: int = 0
    last_enriched_at: Optional[str] = None
    source_references: List[str] = []
    description: Optional[str] = None
    verification_status: str
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
