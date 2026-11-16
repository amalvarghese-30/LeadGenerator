from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CompetitorDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    business_category: Optional[str] = None
    social_profiles: List[Dict[str, str]] = Field(default_factory=list)  # [{platform, url}]
    services: List[str] = Field(default_factory=list)
    ad_references: List[Dict[str, Any]] = Field(default_factory=list)
    client_references: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None
    last_research_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
