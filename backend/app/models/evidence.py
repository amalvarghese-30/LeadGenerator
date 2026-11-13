from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    provider_id: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    evidence_type: str  # webpage|press_release|case_study|social_post|job_listing|news|rss|api
    title: Optional[str] = None
    url: str
    snippet: Optional[str] = None
    full_text: Optional[str] = None
    published_at: Optional[datetime] = None
    crawled_at: Optional[datetime] = None
    relevance_score: float = 0.5
    entities_extracted: Dict = Field(default_factory=dict)  # {people, orgs, services, ...}
    tags: List[str] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
