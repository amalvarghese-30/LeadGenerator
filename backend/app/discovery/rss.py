"""RSS and Atom feed discovery and parsing with stealth browser headers."""
import httpx
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from urllib.parse import urljoin

from app.utils.http_client import get_stealth_headers

logger = logging.getLogger(__name__)

COMMON_FEED_PATHS = [
    "/feed/",
    "/feed.xml",
    "/rss.xml",
    "/rss/",
    "/atom.xml",
    "/blog/feed/",
    "/news/feed/",
    "/index.xml",
    "/feed/atom/",
]


class RSSDiscovery:
    async def discover_feeds(self, base_url: str, homepage_html: str = None) -> List[str]:
        """Find feeds via autodiscovery in HTML + common paths."""
        feeds = []
        seen = set()
        base = base_url.rstrip("/")

        # 1. Check <link rel="alternate" type="application/rss+xml">
        if homepage_html:
            try:
                soup = BeautifulSoup(homepage_html, "lxml")
                for link in soup.find_all("link", rel="alternate"):
                    if link.get("type") in ("application/rss+xml", "application/atom+xml"):
                        href = link.get("href", "")
                        if href:
                            absolute = urljoin(base_url, href)
                            if absolute not in seen:
                                seen.add(absolute)
                                feeds.append(absolute)
            except Exception as e:
                logger.debug(f"HTML feed discovery failed: {e}")

        # 2. If no feeds found in HTML, try common paths with stealth headers
        if not feeds:
            headers = get_stealth_headers(url=base_url)
            async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers, http2=True) as client:
                for path in COMMON_FEED_PATHS:
                    url = base + path
                    if url in seen:
                        continue
                    try:
                        resp = await client.head(url)
                        if resp.status_code == 200:
                            content_type = resp.headers.get("content-type", "")
                            if any(t in content_type for t in ("xml", "rss", "atom", "json")):
                                seen.add(url)
                                feeds.append(url)
                    except Exception:
                        pass

        # 3. Attempt homepage fetch if no HTML provided
        if not feeds and not homepage_html:
            try:
                headers = get_stealth_headers(url=base_url)
                async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers, http2=True) as client:
                    resp = await client.get(base_url)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in soup.find_all("link", rel="alternate"):
                        if link.get("type") in ("application/rss+xml", "application/atom+xml"):
                            href = link.get("href", "")
                            if href:
                                absolute = urljoin(base_url, href)
                                if absolute not in seen:
                                    seen.add(absolute)
                                    feeds.append(absolute)
            except Exception as e:
                logger.debug(f"Homepage fetch for feeds failed: {e}")

        return feeds

    async def parse_feed(self, feed_url: str) -> List[Dict]:
        """Parse feed URL into list of: {url, source, published, title, description}"""
        try:
            headers = get_stealth_headers(url=feed_url)
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers, http2=True) as client:
                resp = await client.get(feed_url)

            if resp.status_code != 200:
                return []

            parsed = feedparser.parse(resp.content)
            items = []
            for entry in parsed.entries:
                link = entry.get("link", "")
                if not link:
                    continue

                items.append({
                    "url": link,
                    "source": "rss",
                    "title": entry.get("title", ""),
                    "published": entry.get("published", "") or entry.get("updated", ""),
                    "description": entry.get("summary", "")[:300] if entry.get("summary") else "",
                    "priority": 60,
                })

            return items
        except Exception as e:
            logger.debug(f"Failed to parse feed {feed_url}: {e}")
            return []
