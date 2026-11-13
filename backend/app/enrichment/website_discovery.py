"""
Official Company & Personal Website Discovery using DDGS, URL heuristics, and domain verification.
Zero-paid-API discovery of legitimate official websites.
"""
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse
from app.discovery.ddgs_search import DDGSSearch
from app.utils.url_utils import extract_domain, normalize_url
from app.utils.deduplication import normalize_string

logger = logging.getLogger(__name__)

# Domains to ignore when looking for official company sites
SOCIAL_AND_DIRECTORY_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "wikipedia.org", "crunchbase.com", "bloomberg.com",
    "dnb.com", "zoominfo.com", "pitchbook.com", "glassdoor.com",
    "indeed.com", "yellowpages.com", "justdial.com", "indiamart.com",
    "zaubacorp.com", "tofler.in", "instafinancials.com", "tracxn.com",
    "craft.co", "apollo.io", "lusha.com", "rocketreach.co", "growjo.com",
    "cbinsights.com", "owler.com", "ambitionbox.com", "clutch.co",
    "goodfirms.co", "themanifest.com", "g2.com", "capterra.com", "trustpilot.com"
}


class WebsiteDiscovery:
    def __init__(self):
        self.searcher = DDGSSearch(max_results=5)

    def discover_company_website(self, company_name: str, country: Optional[str] = "India") -> Optional[str]:
        """Discover official company website using DDGS."""
        if not company_name or len(company_name.strip()) < 3:
            return None

        clean_name = company_name.strip()
        query = f'"{clean_name}" official website'
        try:
            results = self.searcher.search(query, region="in-en")
            for res in results:
                url = res.get("url") or ""
                domain = extract_domain(url).lower()
                if not domain:
                    continue
                # Skip social platforms and generic directories
                if any(ignored in domain for ignored in SOCIAL_AND_DIRECTORY_DOMAINS):
                    continue

                # Verification: domain or title should strongly match company name
                name_tokens = [t for t in normalize_string(clean_name).split() if len(t) > 2]
                domain_clean = domain.replace("-", "").replace(".", "")
                domain_matches = any(tok in domain_clean for tok in name_tokens)
                title_matches = any(tok in res.get("title", "").lower() for tok in name_tokens)

                # Prioritize official domains where the company name appears in the domain itself
                if domain_matches or (title_matches and not any(ind in domain for ind in ["directory", "wiki", "portal", "profile", "listing", "review", "database", "analytics"])):
                    parsed = urlparse(url)
                    root_url = f"{parsed.scheme}://{parsed.netloc}"
                    return root_url
        except Exception as e:
            logger.warning(f"Company website discovery failed for '{company_name}': {e}")

        return None

    def discover_personal_website(self, person_name: str, company_name: Optional[str] = None) -> Optional[str]:
        """Discover personal or professional portfolio/bio website of an individual."""
        if not person_name or len(person_name.strip()) < 3:
            return None

        q = f'"{person_name}" official website'
        if company_name:
            q = f'"{person_name}" "{company_name}" official website'

        try:
            results = self.searcher.search(q, region="wt-wt")
            for res in results:
                url = res.get("url") or ""
                domain = extract_domain(url).lower()
                if not domain:
                    continue
                if any(ignored in domain for ignored in SOCIAL_AND_DIRECTORY_DOMAINS):
                    continue

                title = res.get("title", "").lower()
                snippet = res.get("snippet", "").lower()
                # Check for person name in title / snippet / domain
                name_parts = person_name.lower().split()
                if all(part in f"{title} {domain} {snippet}" for part in name_parts):
                    return url
        except Exception as e:
            logger.warning(f"Personal website discovery failed for '{person_name}': {e}")

        return None
