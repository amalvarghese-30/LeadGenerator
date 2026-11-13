import re
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse
import tldextract


def normalize_url(url: str) -> str:
    """Normalize a URL: lowercase scheme+host, remove default ports, strip trailing slashes."""
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.hostname.lower() if parsed.hostname else ""
    # Include non-default port
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{netloc}:{port}"
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
    return normalized


def extract_domain(url: str) -> Optional[str]:
    """Extract the registered domain (e.g. 'example.com') from a URL."""
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ext = tldextract.extract(url)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return None


def extract_subdomain(url: str) -> str:
    """Return the full subdomain, e.g. 'www' or 'blog'."""
    ext = tldextract.extract(url)
    return ext.subdomain or ""


def is_same_domain(url1: str, url2: str) -> bool:
    """Return True if both URLs share the same registered domain."""
    d1 = extract_domain(url1)
    d2 = extract_domain(url2)
    if d1 and d2:
        return d1.lower() == d2.lower()
    return False


def make_absolute(base_url: str, relative_url: str) -> str:
    """Convert a relative URL to absolute using the base URL."""
    return urljoin(base_url, relative_url)


def clean_url(url: str) -> str:
    """Remove tracking parameters and fragments from a URL."""
    tracking_params = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "msclkid", "ref", "source",
    }
    parsed = urlparse(url)
    if parsed.query:
        from urllib.parse import parse_qs, urlencode
        params = parse_qs(parsed.query, keep_blank_values=True)
        clean_params = {k: v for k, v in params.items() if k.lower() not in tracking_params}
        clean_query = urlencode(clean_params, doseq=True)
    else:
        clean_query = ""
    cleaned = urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, clean_query, ""  # strip fragment
    ))
    return cleaned
