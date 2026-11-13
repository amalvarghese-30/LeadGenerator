"""
SearXNG search client (Optional self-hosted search integration).
"""
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class SearXNGClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.SEARXNG_BASE_URL or "").rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def search(self, query: str, categories: str = "general", max_results: int = 15) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return []
        try:
            async with httpx.AsyncClient(timeout=settings.SEARXNG_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={"q": query, "format": "json", "categories": categories}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("results", [])[:max_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", ""),
                            "source": "searxng",
                        })
                    return results
        except Exception as e:
            logger.debug(f"SearXNG query failed: {e}")
        return []
