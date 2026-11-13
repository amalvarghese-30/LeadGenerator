"""Multi-format sitemap parser with recursive index support."""
import httpx
import xml.etree.ElementTree as ET
import gzip
import io
from typing import List, Dict, Optional
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap.xml.gz",
    "/news-sitemap.xml",
    "/page-sitemap.xml",
]

# XML namespaces used in sitemaps
NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
}

MAX_RECURSION_DEPTH = 5


class SitemapParser:
    def __init__(self, timeout: int = 15, max_urls: int = 5000):
        self.timeout = timeout
        self.max_urls = max_urls
        self._visited_sitemaps: set = set()

    async def discover(self, base_url: str, sitemap_hints: List[str] = None) -> List[Dict]:
        """
        Try all known sitemap paths + provided hints.
        Returns list of: {url, source, lastmod, changefreq, priority}
        """
        self._visited_sitemaps = set()
        all_urls: Dict[str, Dict] = {}
        base = base_url.rstrip("/")

        # Gather all candidate sitemap URLs to try
        candidates = list(sitemap_hints or [])
        for path in SITEMAP_PATHS:
            candidates.append(base + path)

        for sitemap_url in candidates:
            if len(all_urls) >= self.max_urls:
                break
            try:
                items = await self.parse_sitemap_url(sitemap_url, depth=0)
                for item in items:
                    url = item.get("url")
                    if url and url not in all_urls:
                        all_urls[url] = item
            except Exception as e:
                logger.debug(f"Sitemap candidate {sitemap_url} failed: {e}")

        return list(all_urls.values())[:self.max_urls]

    async def parse_sitemap_url(self, url: str, depth: int = 0) -> List[Dict]:
        """Parse a single sitemap URL, recursing into sitemap indexes."""
        if depth > MAX_RECURSION_DEPTH:
            logger.debug(f"Max recursion depth reached for {url}")
            return []

        if url in self._visited_sitemaps:
            return []
        self._visited_sitemaps.add(url)

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "LeadIntel-Researcher/1.0"})

            if resp.status_code != 200:
                logger.debug(f"Sitemap {url} returned HTTP {resp.status_code}")
                return []

            content = resp.content

            # Decompress if gzipped
            if url.endswith(".gz") or resp.headers.get("content-type", "").startswith("application/x-gzip"):
                try:
                    content = self._decompress_gz(content)
                except Exception as e:
                    logger.debug(f"Failed to decompress {url}: {e}")
                    return []

            items = self._parse_xml(content)

            # If items contain sitemap index entries, recurse
            index_urls = [i for i in items if i.get("_is_index")]
            url_items = [i for i in items if not i.get("_is_index")]

            for index_item in index_urls:
                sub_url = index_item.get("url")
                if sub_url:
                    sub_items = await self.parse_sitemap_url(sub_url, depth=depth + 1)
                    url_items.extend(sub_items)

            # Clean internal keys
            for item in url_items:
                item.pop("_is_index", None)

            return url_items

        except httpx.TimeoutException:
            logger.debug(f"Timeout fetching sitemap {url}")
            return []
        except Exception as e:
            logger.debug(f"Error parsing sitemap {url}: {e}")
            return []

    def _parse_xml(self, content: bytes) -> List[Dict]:
        """Parse XML sitemap content, handling indexes and URL sets."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.debug(f"XML parse error: {e}")
            return []

        # Strip namespace for tag comparison
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        items = []

        if tag == "sitemapindex":
            # Sitemap index — each child is a <sitemap> pointing to another sitemap
            for sitemap_el in root:
                child_tag = sitemap_el.tag.split("}")[-1] if "}" in sitemap_el.tag else sitemap_el.tag
                if child_tag == "sitemap":
                    loc_el = sitemap_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                    if loc_el is None:
                        loc_el = sitemap_el.find("loc")
                    if loc_el is not None and loc_el.text:
                        items.append({
                            "url": loc_el.text.strip(),
                            "source": "sitemap_index",
                            "_is_index": True,
                        })

        elif tag == "urlset":
            # Regular URL set
            for url_el in root:
                child_tag = url_el.tag.split("}")[-1] if "}" in url_el.tag else url_el.tag
                if child_tag != "url":
                    continue

                loc_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                if loc_el is None:
                    loc_el = url_el.find("loc")
                if loc_el is None or not loc_el.text:
                    continue

                lastmod_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
                if lastmod_el is None:
                    lastmod_el = url_el.find("lastmod")

                changefreq_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq")
                if changefreq_el is None:
                    changefreq_el = url_el.find("changefreq")

                priority_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}priority")
                if priority_el is None:
                    priority_el = url_el.find("priority")

                items.append({
                    "url": loc_el.text.strip(),
                    "source": "sitemap",
                    "lastmod": lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None,
                    "changefreq": changefreq_el.text.strip() if changefreq_el is not None and changefreq_el.text else None,
                    "priority": float(priority_el.text.strip()) if priority_el is not None and priority_el.text else None,
                })

        return items

    def _decompress_gz(self, content: bytes) -> bytes:
        """Decompress gzip content."""
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
            return f.read()
