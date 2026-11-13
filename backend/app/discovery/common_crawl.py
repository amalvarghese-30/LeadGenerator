"""
Public Common Crawl CDX Index integration for historical URL discovery.
Queries publicly accessible index without downloading bulk datasets.
"""
import logging
import json
from typing import List, Dict, Any
import httpx
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

# Standard available index endpoint
COMMON_CRAWL_INDEX_API = "https://index.commoncrawl.org/CC-MAIN-2024-10-index"

class CommonCrawlDiscovery:
    def __init__(self, index_url: str = COMMON_CRAWL_INDEX_API, timeout: int = 15):
        self.index_url = index_url
        self.timeout = timeout

    async def discover_urls(self, domain: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Query Common Crawl index for known URLs for a domain."""
        if not domain:
            return []

        results: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    self.index_url,
                    params={
                        "url": f"*.{domain}",
                        "output": "json",
                        "limit": max_results,
                        "filter": "=status:200",
                        "fl": "url,timestamp,mime,status",
                    }
                )

                if resp.status_code == 200:
                    for line in resp.text.strip().split("\n"):
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                            url = record.get("url")
                            if url and is_safe_url(url)[0]:
                                results.append({
                                    "url": url,
                                    "timestamp": record.get("timestamp"),
                                    "source": "common_crawl",
                                    "is_historical": True,
                                })
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.debug(f"Common Crawl query for {domain} skipped or unavailable: {e}")

        return results
