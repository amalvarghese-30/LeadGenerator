"""Robots.txt fetcher and parser."""
import httpx
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from typing import Optional, List
import logging
import io

logger = logging.getLogger(__name__)


class RobotsChecker:
    def __init__(self, user_agent: str = "LeadIntel-Researcher/1.0"):
        self.user_agent = user_agent
        self._cache: dict = {}  # base_url -> robots content str

    def _get_base_url(self, url: str) -> str:
        """Extract scheme + host from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def fetch(self, base_url: str) -> Optional[str]:
        """Fetch robots.txt content. Returns content string or None."""
        if base_url in self._cache:
            return self._cache[base_url]

        robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                )
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
                sitemap_url = line[len("sitemap:"):].strip()
                if sitemap_url:
                    sitemaps.append(sitemap_url)
        return sitemaps

    async def is_allowed(self, url: str, base_url: str) -> bool:
        """Check if URL is allowed for crawling by our user-agent."""
        base = self._get_base_url(base_url) if base_url else self._get_base_url(url)
        content = await self.fetch(base)
        if not content:
            # No robots.txt — allow all
            return True
        try:
            rp = RobotFileParser()
            rp.parse(content.splitlines())
            return rp.can_fetch(self.user_agent, url)
        except Exception as e:
            logger.debug(f"robots.txt parse error: {e}")
            return True  # Default to allowing if parse fails

    async def get_crawl_delay(self, base_url: str) -> Optional[float]:
        """Get Crawl-delay directive for our user-agent (or wildcard)."""
        content = await self.fetch(base_url)
        if not content:
            return None
        try:
            rp = RobotFileParser()
            rp.parse(content.splitlines())
            delay = rp.crawl_delay(self.user_agent)
            if delay is None:
                delay = rp.crawl_delay("*")
            return float(delay) if delay is not None else None
        except Exception:
            return None
