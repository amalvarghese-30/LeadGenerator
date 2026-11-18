"""
Client Website Resolver.
Resolves and validates official client company websites with SSRF protection,
redirect hop verification, canonical domain extraction, and public search fallback.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import httpx
import tldextract

from app.discovery.ddgs_search import DDGSSearch
from app.discovery.url_normalizer import URLNormalizer
from app.utils.ssrf_guard import is_safe_url
from app.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

# Excluded domains for company websites (social networks, directories, CDNs, app stores)
DIRECTORY_AND_SOCIAL_DOMAINS = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "github.com", "wikipedia.org", "wikimedia.org", "wa.me",
    "whatsapp.com", "pinterest.com", "reddit.com", "medium.com", "crunchbase.com",
    "zoominfo.com", "justdial.com", "indiamart.com", "yellowpages.com",
    "yelp.com", "glassdoor.com", "play.google.com", "apps.apple.com",
    "amazon.com", "flipkart.com", "cloudflare.com", "w3.org", "schema.org",
}

PARKED_DOMAIN_INDICATORS = [
    "this domain is for sale", "buy this domain", "domain parked",
    "parked free", "godaddy parking", "hugedomains", "dan.com",
    "domain name has expired", "inquire about this domain",
]


class ClientWebsiteResolver:
    def __init__(self, timeout_seconds: float = 10.0, max_redirects: int = 5):
        self.timeout = timeout_seconds
        self.max_redirects = max_redirects
        self.normalizer = URLNormalizer()
        self.ddgs = DDGSSearch(max_results=5)

    async def resolve_client_website(
        self,
        company_name: str,
        portfolio_url: Optional[str] = None,
        provider_domain: Optional[str] = None,
        portfolio_source_url: Optional[str] = None,
        evidence: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve official client website following strict priority:
          1. Portfolio-provided outbound URL
          2. Safe public search discovery fallback
        """
        clean_name = (company_name or "").strip()
        prov_dom = (provider_domain or (extract_domain(portfolio_source_url) if portfolio_source_url else "") or "").lower().replace("www.", "")

        # 1. First Priority: Outbound URL extracted directly from portfolio card
        if portfolio_url and portfolio_url.strip():
            target_url = portfolio_url.strip()
            if not target_url.startswith(("http://", "https://")):
                target_url = f"https://{target_url}"

            val_res = await self._validate_and_follow_url(target_url, prov_dom)
            if val_res.get("is_valid"):
                return {
                    "resolved_url": val_res["final_url"],
                    "official_website": val_res["final_url"],
                    "domain": val_res["domain"],
                    "resolution_source": "portfolio_card",
                    "confidence": 0.95,
                    "status": "valid",
                    "http_status": val_res.get("http_status"),
                    "error": None,
                    "original_candidate_url": portfolio_url,
                }
            else:
                logger.debug("Portfolio URL %s failed validation: %s", target_url, val_res.get("error"))

        # 2. Second Priority: Public Search Discovery if company name is available
        if clean_name and len(clean_name) >= 3:
            search_query = f'"{clean_name}" official website'
            try:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, self.ddgs.search, search_query)
                for item in results:
                    found_url = item.get("url")
                    if not found_url:
                        continue
                    found_domain = self.normalizer.extract_domain(found_url)
                    if not found_domain:
                        continue

                    clean_found_dom = found_domain.lower()
                    if clean_found_dom == prov_dom or clean_found_dom.endswith("." + prov_dom):
                        continue
                    if any(clean_found_dom == exc or clean_found_dom.endswith("." + exc) for exc in DIRECTORY_AND_SOCIAL_DOMAINS):
                        continue

                    val_res = await self._validate_and_follow_url(found_url, prov_dom)
                    if val_res.get("is_valid"):
                        return {
                            "resolved_url": val_res["final_url"],
                            "official_website": val_res["final_url"],
                            "domain": val_res["domain"],
                            "resolution_source": "search_discovery",
                            "confidence": 0.70,
                            "status": "valid",
                            "http_status": val_res.get("http_status"),
                            "error": None,
                            "original_candidate_url": found_url,
                        }
            except Exception as se_err:
                logger.warning("[WEBSITE_RESOLVER] search discovery error for '%s': %s", clean_name, se_err)

        return {
            "resolved_url": None,
            "official_website": None,
            "domain": None,
            "resolution_source": "none",
            "confidence": 0.0,
            "status": "unresolved",
            "http_status": None,
            "error": "No verified official website discovered",
            "original_candidate_url": portfolio_url,
        }

    async def _validate_and_follow_url(self, start_url: str, provider_domain: str) -> Dict[str, Any]:
        """
        Validate URL with SSRF protection and follow redirects up to max_redirects.
        Re-validates SSRF at EVERY redirect hop.
        """
        current_url = start_url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        for hop in range(self.max_redirects + 1):
            # SSRF validation at every hop
            is_safe, reason = is_safe_url(current_url)
            if not is_safe:
                return {"is_valid": False, "error": f"ssrf_blocked_hop_{hop}: {reason}"}

            host = urlparse(current_url).hostname or ""
            clean_host = host.lower().replace("www.", "")
            if clean_host == provider_domain or clean_host.endswith("." + provider_domain):
                return {"is_valid": False, "error": "redirected_to_provider_domain"}

            ext = tldextract.extract(current_url)
            reg_domain = f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else None
            if not reg_domain or any(reg_domain == exc or reg_domain.endswith("." + exc) for exc in DIRECTORY_AND_SOCIAL_DOMAINS):
                return {"is_valid": False, "error": "excluded_social_or_directory_domain"}

            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, headers=headers) as client:
                    resp = await client.get(current_url)
                    status = resp.status_code

                    # Handle Redirects manually to enforce per-hop SSRF validation
                    if status in (301, 302, 303, 307, 308) and "location" in resp.headers:
                        loc = resp.headers["location"]
                        current_url = urljoin(current_url, loc)
                        continue

                    # If successful 200 OK
                    if status == 200:
                        content_type = resp.headers.get("content-type", "").lower()
                        if "html" not in content_type and "text" not in content_type:
                            return {"is_valid": False, "error": f"unsupported_content_type: {content_type}"}

                        # Check parked domain text indicators
                        text_sample = (resp.text or "")[:8000].lower()
                        if any(ind in text_sample for ind in PARKED_DOMAIN_INDICATORS):
                            return {"is_valid": False, "error": "parked_domain"}

                        return {
                            "is_valid": True,
                            "final_url": current_url,
                            "domain": reg_domain,
                            "http_status": status,
                        }
                    else:
                        # Non-200 status code
                        return {"is_valid": False, "error": f"http_status_{status}"}

            except httpx.TimeoutException:
                return {"is_valid": False, "error": "timeout"}
            except httpx.ConnectError:
                return {"is_valid": False, "error": "connection_refused"}
            except Exception as e:
                return {"is_valid": False, "error": str(e)}

        return {"is_valid": False, "error": "too_many_redirects"}
