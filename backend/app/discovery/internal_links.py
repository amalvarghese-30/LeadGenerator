"""
Breadth-first internal link crawler with SSRF protection, domain boundary respect,
path prioritization and canonicalization.
"""
import asyncio
import logging
from collections import deque
from typing import List, Dict, Set, Optional, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

from app.discovery.url_normalizer import URLNormalizer
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

PRIORITY_KEYWORDS = [
    "about", "services", "service", "clients", "client", "portfolio",
    "case-studies", "case-study", "testimonials", "testimonial",
    "our-work", "work", "success-stories", "customers", "team",
    "results", "founder", "contact"
]

class InternalLinkCrawler:
    def __init__(self, max_pages: int = 50, max_depth: int = 3, delay: float = 0.5, timeout: int = 15):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.timeout = timeout
        self.normalizer = URLNormalizer()

    async def discover(self, start_url: str) -> List[Dict[str, Any]]:
        """
        BFS internal link discovery from start_url.
        """
        is_safe, reason = is_safe_url(start_url)
        if not is_safe:
            logger.warning(f"Internal link crawl start_url rejected by SSRF guard: {reason}")
            return []

        base_domain = self.normalizer.extract_domain(start_url)
        if not base_domain:
            return []

        visited: Set[str] = set()
        queue: deque = deque([(self.normalizer.normalize(start_url), 0, None)])
        results: List[Dict[str, Any]] = []

        headers = {
            "User-Agent": "LeadIntel-Researcher/1.0 (internal-link-discovery)"
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            while queue and len(visited) < self.max_pages:
                current_url, depth, parent_url = queue.popleft()
                norm_url = self.normalizer.normalize(current_url)

                if norm_url in visited or depth > self.max_depth:
                    continue

                safe, _ = is_safe_url(norm_url)
                if not safe:
                    continue

                visited.add(norm_url)

                try:
                    resp = await client.get(norm_url)
                    content_type = resp.headers.get("content-type", "")
                    if resp.status_code == 200 and "text/html" in content_type:
                        page_type = self._classify_page(norm_url)
                        priority = self._calculate_priority(norm_url, page_type)

                        results.append({
                            "url": norm_url,
                            "depth": depth,
                            "source_url": parent_url,
                            "page_type": page_type,
                            "priority_score": priority,
                            "status_code": resp.status_code,
                        })

                        # Extract internal links
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for a in soup.find_all("a", href=True):
                            href = a["href"].strip()
                            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                                continue
                            full_url = urljoin(norm_url, href)
                            if self.normalizer.is_same_domain(full_url, norm_url):
                                normalized_child = self.normalizer.normalize(full_url)
                                if normalized_child not in visited:
                                    queue.append((normalized_child, depth + 1, norm_url))

                    await asyncio.sleep(self.delay)
                except Exception as e:
                    logger.debug(f"Error crawling {norm_url}: {e}")

        # Sort by priority score descending
        results.sort(key=lambda x: x["priority_score"], reverse=True)
        return results

    def _classify_page(self, url: str) -> str:
        url_lower = url.lower()
        if any(k in url_lower for k in ["case-study", "case-studies", "results"]):
            return "case_study"
        if any(k in url_lower for k in ["testimonial", "review"]):
            return "testimonial"
        if any(k in url_lower for k in ["portfolio", "our-work", "work"]):
            return "portfolio"
        if any(k in url_lower for k in ["client", "customer"]):
            return "client_list"
        if any(k in url_lower for k in ["about", "founder", "team"]):
            return "about"
        if any(k in url_lower for k in ["service", "what-we-do"]):
            return "services"
        if "contact" in url_lower:
            return "contact"
        return "general"

    def _calculate_priority(self, url: str, page_type: str) -> int:
        type_weights = {
            "case_study": 95,
            "testimonial": 90,
            "portfolio": 85,
            "client_list": 80,
            "about": 70,
            "services": 65,
            "contact": 60,
            "general": 30,
        }
        return type_weights.get(page_type, 30)
