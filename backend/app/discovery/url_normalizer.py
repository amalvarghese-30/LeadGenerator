"""URL normalization and deduplication utilities."""
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, urljoin
import re
from typing import Optional, List
import tldextract

# Tracking query params that should be stripped for deduplication
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "source", "_ga", "mc_cid",
    "mc_eid", "yclid", "gbraid", "wbraid", "twclid", "igshid",
}


class URLNormalizer:
    def normalize(self, url: str) -> str:
        """Normalize URL for deduplication: lowercase, remove fragment, sort query params."""
        if not url or not isinstance(url, str):
            return ""
        try:
            parsed = urlparse(url.strip())
            # Lowercase scheme and netloc
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            # Remove trailing slash from path (except for root)
            path = parsed.path
            if path != "/" and path.endswith("/"):
                path = path.rstrip("/")
            # Sort query params for deterministic comparison
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=True)
                sorted_query = urlencode(sorted(params.items()), doseq=True)
            else:
                sorted_query = ""
            # Drop fragment
            normalized = urlunparse((scheme, netloc, path, parsed.params, sorted_query, ""))
            return normalized
        except Exception:
            return url

    def extract_domain(self, url: str) -> Optional[str]:
        """Extract registered domain (e.g. 'example.com') from a URL."""
        if not url:
            return None
        try:
            extracted = tldextract.extract(url)
            if extracted.domain and extracted.suffix:
                return f"{extracted.domain}.{extracted.suffix}"
            return None
        except Exception:
            return None

    def extract_subdomain_domain(self, url: str) -> Optional[str]:
        """Extract full host (subdomain + domain + suffix), e.g. 'www.example.com'."""
        if not url:
            return None
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().split(":")[0] or None
        except Exception:
            return None

    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Return True if both URLs share the same registered domain."""
        return self.extract_domain(url1) == self.extract_domain(url2)

    def is_internal(self, url: str, base_domain: str) -> bool:
        """Return True if the URL belongs to base_domain."""
        url_domain = self.extract_domain(url)
        return url_domain == base_domain if url_domain else False

    def remove_query_params(self, url: str, params_to_remove: List[str] = None) -> str:
        """Remove tracking params (or a custom list) from URL."""
        if not url:
            return url
        to_remove = set(params_to_remove) if params_to_remove else TRACKING_PARAMS
        try:
            parsed = urlparse(url)
            if not parsed.query:
                return url
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in params.items() if k not in to_remove}
            new_query = urlencode(sorted(filtered.items()), doseq=True)
            return urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, ""
            ))
        except Exception:
            return url

    def make_absolute(self, url: str, base_url: str) -> str:
        """Convert relative URL to absolute using base_url."""
        if not url:
            return ""
        return urljoin(base_url, url)
