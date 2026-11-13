"""
Central Discovery Orchestrator.
Runs all adapters concurrently. Guarantees the start URL is always included
so the crawler has something to work with even if every adapter fails.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any

from app.discovery.sitemap import SitemapParser
from app.discovery.robots import RobotsChecker
from app.discovery.rss import RSSDiscovery
from app.discovery.internal_links import InternalLinkCrawler
from app.discovery.cms_discovery import CMSDiscovery
from app.discovery.common_crawl import CommonCrawlDiscovery
from app.discovery.wayback import WaybackDiscovery
from app.discovery.url_normalizer import URLNormalizer
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

# Keywords that mark a URL as client-reference relevant for priority boosting
PRIORITY_KEYWORDS = {
    "case-study", "case-studies", "testimonial", "testimonials", "client",
    "clients", "portfolio", "our-work", "success-stories", "customer",
    "customers", "results", "founder", "about", "services", "team",
}


class DiscoveryManager:
    def __init__(self):
        self.sitemap_parser = SitemapParser()
        self.robots_checker = RobotsChecker()
        self.rss_discovery = RSSDiscovery()
        self.internal_crawler = InternalLinkCrawler(max_pages=30)
        self.cms_discovery = CMSDiscovery()
        self.common_crawl = CommonCrawlDiscovery()
        self.wayback = WaybackDiscovery()
        self.normalizer = URLNormalizer()

    async def discover_all_urls(self, domain_or_url: str) -> Dict[str, Any]:
        start_url = domain_or_url if domain_or_url.startswith("http") else f"https://{domain_or_url}"
        safe, reason = is_safe_url(start_url)
        if not safe:
            return {
                "error": f"SSRF blocked: {reason}",
                "discovered_urls": [{"url": start_url, "source": "fallback"}],
                "sources_breakdown": {},
                "total_unique": 1,
            }

        domain = self.normalizer.extract_domain(start_url)
        all_urls: Dict[str, Dict[str, Any]] = {
            self.normalizer.normalize(start_url): {
                "url": self.normalizer.normalize(start_url),
                "source": "start",
                "metadata": {},
                "discovered_at": datetime.utcnow().isoformat(),
            }
        }
        source_counts: Dict[str, int] = {"start": 1}
        errors: List[str] = []

        robots_sitemaps: List[str] = []
        try:
            robots_sitemaps = await self.robots_checker.get_sitemaps(start_url)
        except Exception as e:
            errors.append(f"robots.txt: {e}")

        async def run_sitemap():
            try:
                items = await self.sitemap_parser.discover(start_url, sitemap_hints=robots_sitemaps)
                return "sitemap", items
            except Exception as e:
                errors.append(f"sitemap: {e}")
                return "sitemap", []

        async def run_rss():
            try:
                feeds = await self.rss_discovery.discover_feeds(start_url)
                out = []
                for f in feeds:
                    out.extend(await self.rss_discovery.parse_feed(f))
                return "rss", out
            except Exception as e:
                errors.append(f"rss: {e}")
                return "rss", []

        async def run_internal():
            try:
                items = await self.internal_crawler.discover(start_url)
                return "internal_links", items
            except Exception as e:
                errors.append(f"internal_links: {e}")
                return "internal_links", []

        async def run_cms():
            try:
                items = await self.cms_discovery.discover_wordpress_urls(start_url)
                return "cms", items
            except Exception as e:
                errors.append(f"cms: {e}")
                return "cms", []

        async def run_common_crawl():
            if not domain:
                return "common_crawl", []
            try:
                return "common_crawl", await self.common_crawl.discover_urls(domain)
            except Exception as e:
                errors.append(f"common_crawl: {e}")
                return "common_crawl", []

        async def run_wayback():
            if not domain:
                return "wayback", []
            try:
                return "wayback", await self.wayback.discover_urls(domain)
            except Exception as e:
                errors.append(f"wayback: {e}")
                return "wayback", []

        results = await asyncio.gather(
            run_sitemap(), run_rss(), run_internal(), run_cms(),
            run_common_crawl(), run_wayback(),
            return_exceptions=True,
        )

        for res in results:
            if not isinstance(res, tuple) or len(res) != 2:
                continue
            source_name, items = res
            count = 0
            for item in items:
                u = item.get("url") if isinstance(item, dict) else str(item)
                if not u or not is_safe_url(u)[0]:
                    continue
                norm = self.normalizer.normalize(u)
                if norm in all_urls:
                    continue
                all_urls[norm] = {
                    "url": norm,
                    "source": source_name,
                    "metadata": item if isinstance(item, dict) else {},
                    "discovered_at": datetime.utcnow().isoformat(),
                }
                count += 1
            source_counts[source_name] = count

        def priority(entry):
            u = entry["url"].lower()
            return 100 if any(k in u for k in PRIORITY_KEYWORDS) else 20

        sorted_urls = sorted(all_urls.values(), key=priority, reverse=True)
        return {
            "target": start_url,
            "domain": domain,
            "total_unique": len(sorted_urls),
            "sources_breakdown": source_counts,
            "discovered_urls": sorted_urls,
            "errors": errors,
            "completed_at": datetime.utcnow().isoformat(),
        }