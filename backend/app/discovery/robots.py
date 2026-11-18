"""Robots.txt fetcher and parser with stealth browser headers."""
import httpx
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from typing import Optional, List
import logging
import io

from app.utils.http_client import get_stealth_headers

logger = logging.getLogger(__name__)


class RobotsChecker:
    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent
        self._cache: dict = {}  # base_url -> robots content str

    def _get_base_url(self, url: str) -> str:
        """Extract scheme + host from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def fetch(self, base_url: str) -> Optional[str]:
        """Fetch robots.txt content using realistic browser headers. Returns content string or None."""
        if base_url in self._cache:
            return self._cache[base_url]

        robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
        try:
            headers = get_stealth_headers(url=robots_url)
            async with httpx.AsyncClient(timeout=10, follow_redirects=True, http2=True) as client:
                resp = await client.get(robots_url, headers=headers)
            if resp.status_code == 200:
                content = resp.text
                self._cache[base_url] = content
                return content
            else:
                self._cache[base_url] = None
                return None
        except Exception as e:
            logger.debug(f"Failed to fetch robots.txt for {base_url}: {e}")
            self._cache[base_url] = None
            return None

    async def get_sitemaps(self, base_url: str) -> List[str]:
        """Extract Sitemap: directives from robots.txt."""
        content = await self.fetch(base_url)
        if not content:
            return []

        sitemaps = []
        for line in content.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    sitemap_url = parts[1].strip()
                    if sitemap_url.startswith("http"):
                        sitemaps.append(sitemap_url)
        return sitemaps

    async def is_allowed(self, base_url: str, url: str) -> bool:
        """Check if URL is allowed for user_agent in robots.txt."""
        content = await self.fetch(base_url)
        if not content:
            return True  # If no robots.txt, assume allowed

        rp = RobotFileParser()
        rp.parse(content.splitlines())
        target_ua = self.user_agent or "*"
        return rp.can_fetch(target_ua, url) or rp.can_fetch("*", url)

    def get_crawl_delay(self, base_url: str) -> Optional[float]:
        """Get crawl-delay directive if present."""
        content = self._cache.get(base_url)
        if not content:
            return None

        rp = RobotFileParser()
        rp.parse(content.splitlines())
        target_ua = self.user_agent or "*"
        delay = rp.crawl_delay(target_ua)
        if delay is None and target_ua != "*":
            delay = rp.crawl_delay("*")
        return float(delay) if delay is not None else None
