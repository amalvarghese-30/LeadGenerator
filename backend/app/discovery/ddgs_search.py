"""
DuckDuckGo search provider via ddgs library.
ZERO paid API dependency. Free and publicly accessible.
Graceful degradation and backoff on rate-limiting.
"""
import logging
import time
from typing import List, Dict, Optional, Any
from app.discovery.url_normalizer import URLNormalizer

logger = logging.getLogger(__name__)

PROVIDER_SEARCH_QUERIES = [
    "Google Knowledge Panel services India",
    "Personal branding agency India",
    "Founder branding services",
    "Executive reputation management",
    "Google entity SEO service",
    "Personal branding for CEOs",
    "LinkedIn personal branding agency",
    "Online reputation management for professionals",
    "Google Knowledge Graph services",
    "Personal profile creation service",
    "Personal profile publishing digital authority",
    "Thought leadership agency executives",
    "Wikipedia biography creation services",
    "Digital PR personal branding agency",
]

class DDGSSearch:
    def __init__(self, region: str = "wt-wt", max_results: int = 15):
        self.region = region
        self.max_results = max_results
        self.normalizer = URLNormalizer()

    def search(self, query: str, region: Optional[str] = None, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Execute DDGS search safely without crashing if blocked or rate-limited.
        """
        results: List[Dict[str, Any]] = []
        eff_region = region or self.region
        eff_limit = max_results or self.max_results

        try:
            # Import dynamically to tolerate missing module
            from ddgs import DDGS
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(
                    query,
                    region=eff_region,
                    max_results=eff_limit
                ))

                for r in raw_results:
                    url = r.get("href") or r.get("url") or ""
                    title = r.get("title") or ""
                    snippet = r.get("body") or r.get("snippet") or ""
                    if url:
                        domain = self.normalizer.extract_domain(url)
                        results.append({
                            "title": title.strip(),
                            "url": self.normalizer.normalize(url),
                            "snippet": snippet.strip(),
                            "domain": domain,
                            "source": "ddgs",
                            "query": query,
                        })
            return results
        except Exception as e:
            logger.warning(f"DDGS search for '{query}' failed gracefully: {e}")
            return []

    def search_providers(self, keywords: Optional[List[str]] = None, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Execute provider discovery searches across multiple variations with polite pacing.
        """
        queries = keywords or PROVIDER_SEARCH_QUERIES
        all_results: List[Dict[str, Any]] = []
        seen_domains = set()

        for query in queries:
            items = self.search(query, region=region)
            for item in items:
                domain = item.get("domain")
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    all_results.append(item)
            # Polite pause to avoid rapid requests
            time.sleep(1.0)

        return all_results

    def generate_dork_queries(self, domain: str) -> List[str]:
        """Generate search operator queries for client discovery."""
        return [
            f'site:{domain} "case study"',
            f'site:{domain} "our clients"',
            f'site:{domain} "testimonials"',
            f'site:{domain} "success stories"',
            f'site:{domain} "founder"',
            f'site:{domain} "personal branding"',
            f'site:{domain} inurl:portfolio',
            f'site:{domain} inurl:case-studies',
            f'site:{domain} inurl:clients',
            f'site:{domain} "worked with" OR "helped"',
        ]
