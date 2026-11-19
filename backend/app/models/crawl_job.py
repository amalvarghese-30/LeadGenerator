from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

CRAWL_STATUSES = [
    "pending", "running", "completed", "completed_with_warnings",
    "failed", "paused", "cancelled",
]

CURRENT_STAGES = [
    "queued", "discovering", "crawling", "extracting",
    "verifying", "creating_crm_records", "enriching_contacts", "generating_report", "completed",
]


class CrawlJobDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    job_type: str = "full_research"
    provider_id: Optional[str] = None
    starting_url: Optional[str] = None
    target_domain: Optional[str] = None

    status: str = "pending"
    current_stage: str = "queued"
    progress_pct: int = 0
    max_pages: int = 50

    # Canonical counters — used everywhere
    pages_discovered: int = 0
    pages_attempted: int = 0
    pages_crawled: int = 0       # successfully fetched AND extracted
    pages_failed: int = 0
    pages_skipped: int = 0
    pages_analysed: int = 0      # successfully fetched pages passed to analysis
    pages_ai_processed: int = 0

    references_found: int = 0
    contacts_created: int = 0
    companies_created: int = 0
    leads_created: int = 0

    errors: List[Dict] = Field(default_factory=list)     # [{stage, url, error_type, message, timestamp}]
    warnings: List[Dict] = Field(default_factory=list)

    discovery_stats: Dict = Field(default_factory=dict)
    ai_stats: Dict = Field(default_factory=dict)

    # Distributed lock
    lock_key: Optional[str] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None

    retry_count: int = 0
    max_retries: int = 2

    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}