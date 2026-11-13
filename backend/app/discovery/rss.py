"""RSS and Atom feed discovery and parsing."""
import httpx
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from urllib.parse import urljoin

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

        # 2. If no feeds found in HTML, try common paths
        if not feeds:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                for path in COMMON_FEED_PATHS:
                    url = base + path
                    if url in seen:
                        continue
                    try:
                        resp = await client.head(
                            url,
                            headers={"User-Agent": "LeadIntel-Researcher/1.0"},
                        )
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
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(
                        base_url,
                        headers={"User-Agent": "LeadIntel-Researcher/1.0"},
                    )
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
        """
        Parse a feed. Returns list of:
        {url, title, published_at, author, description, source}
        """
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    feed_url,
                    headers={"User-Agent": "LeadIntel-Researcher/1.0"},
                )
            if resp.status_code != 200:
                return []

            # feedparser works with string content
            parsed = feedparser.parse(resp.text)
            items = []
            for entry in parsed.entries:
                # Extract URL
                url = entry.get("link") or entry.get("id", "")
                if not url:
                    continue

                # Extract published date
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    from datetime import datetime
                    try:
                        published_at = datetime(*entry.published_parsed[:6]).isoformat()
                    except Exception:
                        pass
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    from datetime import datetime
                    try:
                        published_at = datetime(*entry.updated_parsed[:6]).isoformat()
                    except Exception:
                        pass

                # Extract author
                author = ""
                if hasattr(entry, "author"):
                    author = entry.author
                elif hasattr(entry, "authors") and entry.authors:
                    author = entry.authors[0].get("name", "")

                # Extract description/summary
                description = ""
                if hasattr(entry, "summary"):
                    description = entry.summary
                elif hasattr(entry, "description"):
                    description = entry.description
                # Strip HTML from description
                if description:
                    try:
                        description = BeautifulSoup(description, "lxml").get_text(" ", strip=True)[:500]
                    except Exception:
                        description = description[:500]

                items.append({
                    "url": url,
                    "title": entry.get("title", ""),
                    "published_at": published_at,
                    "author": author,
                    "description": description,
                    "source": "rss",
                    "feed_url": feed_url,
                })

            return items

        except Exception as e:
            logger.debug(f"Failed to parse feed {feed_url}: {e}")
            return []
