from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchHistoryDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    search_type: str  # "company", "individual", "universal"
    query_params: Dict[str, Any]
    results_count: int = 0
    results: List[Dict[str, Any]] = Field(default_factory=list)
    sources_used: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
