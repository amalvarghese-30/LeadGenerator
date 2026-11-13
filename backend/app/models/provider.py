from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ProviderDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    country: Optional[str] = None
    social_profiles: Dict[str, str] = Field(default_factory=dict)  # {linkedin, twitter, github, ...}
    # Category for competitive intelligence
    category: str = "pending_review"  # direct_competitor|close_competitor|adjacent_provider|irrelevant|pending_review
    similarity_score: float = 0.0  # 0.0 - 1.0
    similarity_reasons: List[str] = Field(default_factory=list)
    # Operational status
    discovery_status: str = "discovered"  # discovered|crawling|crawled|error
    verification_status: str = "unverified"  # unverified|pending|verified|rejected
    last_crawled_at: Optional[datetime] = None
    crawl_error: Optional[str] = None
    source: str = "manual"  # manual|ddgs|sitemap|rss|common_crawl|wayback|google_dorking
    # Metadata
    employee_count: Optional[str] = None
    founded_year: Optional[int] = None
    technologies: List[str] = Field(default_factory=list)
    client_industries: List[str] = Field(default_factory=list)
    notable_clients: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
