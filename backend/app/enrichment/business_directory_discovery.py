"""
Public Business Directory & Speaker Discovery:
Discovers conference speaker profiles, industry association member lists,
and public chamber listings matching Person + Company without using any leaked data.
"""
import logging
from typing import List, Dict, Any, Optional
from app.discovery.ddgs_search import DDGSSearch
from app.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

APPROVED_DIRECTORY_PATTERNS = [
    "speaker", "biography", "directory", "association", "chamber",
    "conference", "summit", "forum", "event", "profile", "authors"
]


class BusinessDirectoryDiscovery:
    def __init__(self):
        self.searcher = DDGSSearch(max_results=4)

    def search_directories(
        self,
        person_name: str,
        company_name: Optional[str] = None,
        designation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search public speaker and professional directory profiles."""
        if not person_name:
            return []

        queries = []
        if company_name:
            queries.append(f'"{person_name}" "{company_name}" speaker bio')
            queries.append(f'"{person_name}" "{company_name}" conference speaker')
            queries.append(f'"{person_name}" "{company_name}" directory profile')
        else:
            queries.append(f'"{person_name}" speaker biography')

        discovered: List[Dict[str, Any]] = []
        seen_urls = set()

        for q in queries:
            try:
                results = self.searcher.search(q, region="in-en")
                for r in results:
                    url = r.get("url") or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    domain = extract_domain(url).lower()
                    title = r.get("title", "").lower()
                    snippet = r.get("snippet", "").lower()

                    # Must match person name and at least one directory keyword
                    if person_name.lower() in f"{title} {snippet}":
                        if any(kw in f"{url.lower()} {title}" for kw in APPROVED_DIRECTORY_PATTERNS):
                            discovered.append({
                                "url": url,
                                "domain": domain,
                                "title": r.get("title"),
                                "snippet": r.get("snippet"),
                                "source_type": "public_directory_or_speaker_bio",
                            })
            except Exception as e:
                logger.warning(f"Directory search error for query '{q}': {e}")

        return discovered[:3]
