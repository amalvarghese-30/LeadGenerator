"""
Central Discovery Orchestrator.
- Multi-source discovery:
  1. robots.txt and sitemap references
  2. XML sitemaps
  3. RSS and Atom feeds
  4. Internal website link discovery
  5. Public CMS endpoints (WordPress/Drupal/Ghost)
  6. Search engine results and generated search operators
  7. Common Crawl
  8. Internet Archive (Wayback Machine)
- Stores per-URL: url, discovery_source, discovery_time, page_category, priority, crawl_status.
- Normalises URLs, deduplicates, enforces SSRF protection.
- Configurable limits, source-by-source status reporting.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from app.discovery.sitemap import SitemapParser
from app.discovery.robots import RobotsChecker
from app.discovery.rss import RSSDiscovery
from app.discovery.internal_links import InternalLinkCrawler
from app.discovery.cms_discovery import CMSDiscovery
from app.discovery.common_crawl import CommonCrawlDiscovery
from app.discovery.wayback import WaybackDiscovery
from app.discovery.google_dorking import GoogleDorkingHelper
from app.discovery.ddgs_search import DDGSSearch
from app.discovery.url_normalizer import URLNormalizer
from app.utils.ssrf_guard import is_safe_url
from app.config import settings

logger = logging.getLogger(__name__)

CATEGORY_PATTERNS = {
    "case_study": ["case-study", "case-studies", "success-stories", "our-work", "customer-stories", "results"],
    "testimonial": ["testimonial", "testimonials", "reviews", "endorsements"],
    "portfolio": ["portfolio", "projects", "work", "showcase"],
    "client_list": ["client", "clients", "customer", "customers", "client-list", "who-we-work-with"],
    "founder_profile": ["founder", "leadership", "executive", "biography", "bio", "ceo", "directors"],
    "team_bio": ["team", "about-us", "about", "people", "staff", "meet-the-team"],
    "services": ["services", "solutions", "what-we-do", "capabilities", "offerings"],
}

CATEGORY_PRIORITIES = {
    "case_study": 100,
    "testimonial": 95,
    "portfolio": 90,
    "client_list": 85,
    "founder_profile": 80,
    "team_bio": 70,
    "services": 50,
    "general": 20,
}


def categorize_url(url: str) -> str:
    u = url.lower()
    for cat, keywords in CATEGORY_PATTERNS.items():
        if any(kw in u for kw in keywords):
            return cat
    return "general"


def calculate_priority(category: str) -> int:
    return CATEGORY_PRIORITIES.get(category, 20)


class DiscoveryManager:
    def __init__(self, max_pages: Optional[int] = None):
        self.max_pages = max_pages or getattr(settings, "CRAWLER_MAX_PAGES_PER_JOB", 30)
        self.sitemap_parser = SitemapParser()
        self.robots_checker = RobotsChecker()
        self.rss_discovery = RSSDiscovery()
        self.internal_crawler = InternalLinkCrawler(max_pages=self.max_pages)
        self.cms_discovery = CMSDiscovery()
        self.common_crawl = CommonCrawlDiscovery()
        self.wayback = WaybackDiscovery()
        self.dorking_helper = GoogleDorkingHelper()
        self.ddgs = DDGSSearch(max_results=10)
        self.normalizer = URLNormalizer()

    async def discover_all_urls(
        self,
        domain_or_url: str,
        brand_name: Optional[str] = None,
        max_urls: Optional[int] = None,
    ) -> Dict[str, Any]:
        limit = max_urls or self.max_pages
        start_url = domain_or_url if domain_or_url.startswith("http") else f"https://{domain_or_url}"
        safe, reason = is_safe_url(start_url)
        if not safe:
            return {
                "error": f"SSRF blocked: {reason}",
                "discovered_urls": [{
                    "url": start_url,
                    "discovery_source": "fallback",
                    "discovery_time": datetime.now(timezone.utc).isoformat(),
                    "page_category": "general",
                    "priority": 20,
                    "crawl_status": "skipped",
                }],
                "sources_breakdown": {},
                "sources_status": {},
                "total_unique": 1,
            }

        domain = self.normalizer.extract_domain(start_url)
        now_iso = datetime.now(timezone.utc).isoformat()

        all_urls: Dict[str, Dict[str, Any]] = {
            self.normalizer.normalize(start_url): {
                "url": self.normalizer.normalize(start_url),
                "discovery_source": "start",
                "discovery_time": now_iso,
                "page_category": categorize_url(start_url),
                "priority": calculate_priority(categorize_url(start_url)),
                "crawl_status": "pending",
                "metadata": {},
            }
        }
        source_counts: Dict[str, int] = {"start": 1}
        source_status: Dict[str, str] = {"start": "success"}
        errors: List[str] = []

        # 1. robots.txt
        robots_sitemaps: List[str] = []
        try:
            robots_sitemaps = await self.robots_checker.get_sitemaps(start_url)
            source_status["robots.txt"] = "success"
        except Exception as e:
            errors.append(f"robots.txt: {e}")
            source_status["robots.txt"] = f"failed: {e}"

        # 2. XML Sitemaps
        async def run_sitemap():
            try:
                items = await self.sitemap_parser.discover(start_url, sitemap_hints=robots_sitemaps)
                return "sitemap", items, "success"
            except Exception as e:
                errors.append(f"sitemap: {e}")
                return "sitemap", [], f"failed: {e}"

        # 3. RSS / Atom
        async def run_rss():
            try:
                feeds = await self.rss_discovery.discover_feeds(start_url)
                out = []
                for f in feeds:
                    out.extend(await self.rss_discovery.parse_feed(f))
                return "rss", out, "success"
            except Exception as e:
                errors.append(f"rss: {e}")
                return "rss", [], f"failed: {e}"

        # 4. Internal website links
        async def run_internal():
            try:
                items = await self.internal_crawler.discover(start_url)
                return "internal_links", items, "success"
            except Exception as e:
                errors.append(f"internal_links: {e}")
                return "internal_links", [], f"failed: {e}"

        # 5. Public CMS endpoints
        async def run_cms():
            try:
                items = await self.cms_discovery.discover_wordpress_urls(start_url)
                return "cms", items, "success"
            except Exception as e:
                errors.append(f"cms: {e}")
                return "cms", [], f"failed: {e}"

        # 6. Search engine dorking / operators
        async def run_search_engine_dorking():
            if not domain:
                return "search_operators", [], "skipped"
            try:
                queries = self.dorking_helper.generate_queries(domain, brand_name or "")
                dork_urls = []
                for q in queries[:2]:
                    search_res = self.ddgs.search(q, max_results=5)
                    for sr in search_res:
                        u = sr.get("url")
                        if u and domain in u.lower():
                            dork_urls.append({"url": u, "source": "search_operators"})
                return "search_operators", dork_urls, "success"
            except Exception as e:
                errors.append(f"search_operators: {e}")
                return "search_operators", [], f"failed: {e}"

        # 7. Common Crawl
        async def run_common_crawl():
            if not domain:
                return "common_crawl", [], "skipped"
            try:
                items = await self.common_crawl.discover_urls(domain)
                return "common_crawl", items, "success"
            except Exception as e:
                errors.append(f"common_crawl: {e}")
                return "common_crawl", [], f"failed: {e}"

        # 8. Wayback Machine
        async def run_wayback():
            if not domain:
                return "wayback", [], "skipped"
            try:
                items = await self.wayback.discover_urls(domain)
                return "wayback", items, "success"
            except Exception as e:
                errors.append(f"wayback: {e}")
                return "wayback", [], f"failed: {e}"

        results = await asyncio.gather(
            run_sitemap(),
            run_rss(),
            run_internal(),
            run_cms(),
            run_search_engine_dorking(),
            run_common_crawl(),
            run_wayback(),
            return_exceptions=True,
        )

        for res in results:
            if not isinstance(res, tuple) or len(res) != 3:
                continue
            source_name, items, status = res
            source_status[source_name] = status
            count = 0
            for item in items:
                u = item.get("url") if isinstance(item, dict) else str(item)
                if not u or not is_safe_url(u)[0]:
                    continue
                norm = self.normalizer.normalize(u)
                if norm in all_urls:
                    continue

                category = categorize_url(norm)
                priority = calculate_priority(category)

                all_urls[norm] = {
                    "url": norm,
                    "discovery_source": source_name,
                    "discovery_time": datetime.now(timezone.utc).isoformat(),
                    "page_category": category,
                    "priority": priority,
                    "crawl_status": "pending",
                    "metadata": item if isinstance(item, dict) else {},
                }
                count += 1
            source_counts[source_name] = count

        # Sort strictly by priority descending, keeping highest value leads first
        sorted_urls = sorted(all_urls.values(), key=lambda x: x["priority"], reverse=True)
        # Cap to limit
        capped_urls = sorted_urls[:limit]

        return {
            "target": start_url,
            "domain": domain,
            "total_unique": len(sorted_urls),
            "capped_count": len(capped_urls),
            "sources_breakdown": source_counts,
            "sources_status": source_status,
            "discovered_urls": capped_urls,
            "all_discovered_urls": sorted_urls,
            "errors": errors,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
