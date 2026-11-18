"""
Breadth-first internal link crawler with SSRF protection, domain boundary respect,
path prioritization, canonicalization, and realistic stealth browser headers.
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
from app.utils.http_client import get_stealth_headers, HAS_HTTP2

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

        headers = get_stealth_headers(url=start_url)

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers, http2=HAS_HTTP2) as client:
            while queue and len(visited) < self.max_pages:
                current_url, depth, parent_url = queue.popleft()
                norm_url = self.normalizer.normalize(current_url)

                if norm_url in visited or depth > self.max_depth:
                    continue

                visited.add(norm_url)

                is_safe, reason = is_safe_url(current_url)
                if not is_safe:
                    continue

                try:
                    if len(visited) > 1 and self.delay > 0:
                        await asyncio.sleep(self.delay)

                    # Update referer in headers for realistic navigation
                    page_headers = get_stealth_headers(url=current_url, referer=parent_url)
                    resp = await client.get(current_url, headers=page_headers)

                    if resp.status_code != 200:
                        continue

                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        continue

                    html = resp.text
                    soup = BeautifulSoup(html, "html.parser")

                    # Extract canonical URL if present
                    canonical_url = None
                    canon_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
                    if canon_tag and canon_tag.get("href"):
                        canonical_url = urljoin(current_url, canon_tag["href"].strip())

                    # Record this discovered page
                    results.append({
                        "url": current_url,
                        "canonical_url": canonical_url,
                        "source": "internal_link",
                        "depth": depth,
                        "parent_url": parent_url,
                        "priority": self._score_priority(current_url),
                    })

                    # If at max depth, don't extract child links
                    if depth >= self.max_depth:
                        continue

                    # Extract and enqueue internal links
                    child_links = self._extract_links(soup, current_url, base_domain)
                    child_links.sort(key=lambda u: self._score_priority(u), reverse=True)

                    for child in child_links:
                        norm_child = self.normalizer.normalize(child)
                        if norm_child not in visited:
                            queue.append((child, depth + 1, current_url))

                except Exception as e:
                    logger.debug(f"Failed to crawl internal link {current_url}: {e}")
                    continue

        return results

    def _extract_links(self, soup: BeautifulSoup, base_url: str, base_domain: str) -> List[str]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            absolute = urljoin(base_url, href)
            # Fragment removal
            parsed = urlparse(absolute)
            clean_url = parsed._replace(fragment="").geturl()

            # Domain boundary check: must match base_domain or subdomain
            child_domain = self.normalizer.extract_domain(clean_url)
            if child_domain and (child_domain == base_domain or child_domain.endswith(f".{base_domain}")):
                # Filter out asset extensions
                path = parsed.path.lower()
                if not any(path.endswith(ext) for ext in [
                    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js",
                    ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".woff", ".woff2"
                ]):
                    links.append(clean_url)
        return links

    def _score_priority(self, url: str) -> int:
        u = url.lower()
        for kw in PRIORITY_KEYWORDS:
            if kw in u:
                return 80
        return 30
