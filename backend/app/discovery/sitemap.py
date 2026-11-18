"""Multi-format sitemap parser with recursive index support and stealth headers."""
import httpx
import xml.etree.ElementTree as ET
import gzip
import io
from typing import List, Dict, Optional
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

from app.utils.http_client import get_stealth_headers, HAS_HTTP2

logger = logging.getLogger(__name__)

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/post-sitemap.xml",
    "/portfolio-sitemap.xml",
    "/case-studies-sitemap.xml",
    "/projects-sitemap.xml",
    "/clients-sitemap.xml",
    "/page-sitemap.xml",
    "/sitemap.xml.gz",
    "/news-sitemap.xml",
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
            headers = get_stealth_headers(url=url)
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, http2=HAS_HTTP2) as client:
                resp = await client.get(url, headers=headers)

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
        """Parse raw XML into list of items or index entries."""
        items = []
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            # Try stripping whitespace/BOM and re-parsing
            try:
                cleaned = content.strip().lstrip(b"\xef\xbb\xbf")
                root = ET.fromstring(cleaned)
            except Exception:
                return []

        tag = root.tag.lower()

        # Check for sitemapindex
        if "sitemapindex" in tag:
            for sm in root.findall("sm:sitemap", NS) or root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap") or root.findall("sitemap"):
                loc = sm.findtext("sm:loc", default="", namespaces=NS) or sm.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc") or sm.findtext("loc")
                if loc:
                    items.append({"url": loc.strip(), "source": "sitemap_index", "_is_index": True})
            return items

        # Standard urlset
        for url_elem in root.findall("sm:url", NS) or root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url") or root.findall("url"):
            loc = (
                url_elem.findtext("sm:loc", default="", namespaces=NS)
                or url_elem.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                or url_elem.findtext("loc")
            )
            if not loc:
                continue

            lastmod = (
                url_elem.findtext("sm:lastmod", default="", namespaces=NS)
                or url_elem.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
                or url_elem.findtext("lastmod")
            )
            changefreq = (
                url_elem.findtext("sm:changefreq", default="", namespaces=NS)
                or url_elem.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq")
                or url_elem.findtext("changefreq")
            )
            priority_str = (
                url_elem.findtext("sm:priority", default="", namespaces=NS)
                or url_elem.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}priority")
                or url_elem.findtext("priority")
            )

            try:
                priority = float(priority_str) if priority_str else 0.5
            except ValueError:
                priority = 0.5

            items.append({
                "url": loc.strip(),
                "source": "sitemap",
                "lastmod": lastmod.strip() if lastmod else None,
                "changefreq": changefreq.strip() if changefreq else None,
                "priority": priority,
            })

        return items

    def _decompress_gz(self, data: bytes) -> bytes:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            return gz.read()
