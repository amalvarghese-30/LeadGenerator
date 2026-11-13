from typing import Dict, List, Optional
from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    max_results: int = 20
    search_engines: List[str] = ["ddgs"]
    country_filter: Optional[str] = None
    industry_filter: Optional[str] = None
    exclude_domains: List[str] = []


class DiscoveryJobResponse(BaseModel):
    id: str
    job_type: str
    provider_id: Optional[str] = None
    target_url: Optional[str] = None
    status: str
    progress: float
    urls_discovered: int
    urls_crawled: int
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class DiscoveredUrlResponse(BaseModel):
    url: str
    domain: str
    source: str
    relevance_score: float = 0.0
    discovered_at: str
    metadata: Dict = {}


class ResearchRequest(BaseModel):
    provider_id: str
    force_recrawl: bool = False
    crawl_depth: int = 2
