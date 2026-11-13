from typing import Dict, List, Optional
from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    services: List[str] = []
    location: Optional[str] = None
    country: Optional[str] = None
    social_profiles: Dict[str, str] = {}
    category: str = "pending_review"
    similarity_score: float = 0.0
    similarity_reasons: List[str] = []
    source: str = "manual"
    employee_count: Optional[str] = None
    technologies: List[str] = []
    tags: List[str] = []
    notes: Optional[str] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    services: Optional[List[str]] = None
    location: Optional[str] = None
    country: Optional[str] = None
    social_profiles: Optional[Dict[str, str]] = None
    category: Optional[str] = None
    similarity_score: Optional[float] = None
    similarity_reasons: Optional[List[str]] = None
    discovery_status: Optional[str] = None
    verification_status: Optional[str] = None
    employee_count: Optional[str] = None
    technologies: Optional[List[str]] = None
    notable_clients: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class ProviderResponse(BaseModel):
    id: str
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    services: List[str] = []
    location: Optional[str] = None
    country: Optional[str] = None
    social_profiles: Dict[str, str] = {}
    category: str = "pending_review"
    similarity_score: float = 0.0
    similarity_reasons: List[str] = []
    discovery_status: str = "discovered"
    verification_status: str = "unverified"
    last_crawled_at: Optional[str] = None
    source: str = "manual"
    employee_count: Optional[str] = None
    technologies: List[str] = []
    notable_clients: List[str] = []
    tags: List[str] = []
    notes: Optional[str] = None
    crawl_job_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True, "extra": "ignore"}
