"""
Wayback Machine CDX API integration for historical URL discovery.
Treats retrieved URLs strictly as historical references.
"""
import logging
from typing import List, Dict, Any
import httpx
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

class WaybackDiscovery:
    CDX_API = "https://web.archive.org/cdx/search/cdx"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def discover_urls(self, domain: str, max_results: int = 100) -> List[Dict[str, Any]]:
        if not domain:
            return []

        results: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    self.CDX_API,
                    params={
                        "url": f"*.{domain}/*",
                        "output": "json",
                        "limit": max_results,
                        "filter": "statuscode:200",
                        "fl": "urlkey,timestamp,original,mimetype,statuscode",
                        "collapse": "urlkey",
                    }
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if len(data) > 1:
                        headers = data[0]
                        for row in data[1:]:
                            record = dict(zip(headers, row))
                            url = record.get("original")
                            if url and is_safe_url(url)[0]:
                                results.append({
                                    "url": url,
                                    "timestamp": record.get("timestamp"),
                                    "source": "wayback",
                                    "is_historical": True,
                                })
        except Exception as e:
            logger.debug(f"Wayback discovery for {domain} skipped or unavailable: {e}")

        return results
