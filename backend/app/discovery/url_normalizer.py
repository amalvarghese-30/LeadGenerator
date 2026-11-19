"""URL normalization and deduplication utilities."""
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, urljoin
import re
from typing import Optional, List
import tldextract

# Tracking query params that should be stripped for deduplication
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "source", "_ga", "mc_cid",
    "mc_eid", "yclid", "gbraid", "wbraid", "twclid", "igshid", "_gl",
}

STATIC_ASSET_EXTENSIONS = {
    ".css", ".js", ".mjs", ".map",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp", ".tiff",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".mp3", ".wav", ".avi", ".mov", ".wmv", ".webm", ".m4a", ".ogg",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
    ".exe", ".dmg", ".apk", ".bin", ".iso", ".msi",
    ".csv", ".tsv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

EXCLUDED_PATH_PATTERNS = [
    "/wp-content/plugins/",
    "/wp-content/themes/",
    "/wp-includes/",
    "/cdn-cgi/",
]

EXCLUDED_AUTH_PATTERNS = [
    "/wp-admin",
    "/wp-login",
    "/cart",
    "/checkout",
    "/my-account",
    "/logout",
    "/log-out",
]


def is_crawlable_content_url(url: str) -> bool:
    """
    Returns True if the URL points to genuine website content.
    Filters out static assets, binary downloads, tracking endpoints, and login/admin paths.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in ("http", "https"):
            return False

        path_lower = parsed.path.lower()

        # 1. Reject static asset extensions
        for ext in STATIC_ASSET_EXTENSIONS:
            if path_lower.endswith(ext):
                return False

        # 2. Reject internal CMS asset directories
        for pat in EXCLUDED_PATH_PATTERNS:
            if pat in path_lower:
                return False

        # 3. Reject administrative, cart, and authentication paths
        for pat in EXCLUDED_AUTH_PATTERNS:
            if pat in path_lower:
                return False

        return True
    except Exception:
        return False


class URLNormalizer:
    def normalize(self, url: str, strip_tracking: bool = True) -> str:
        """Normalize URL for deduplication: lowercase scheme/host, strip tracking params, remove fragment."""
        if not url or not isinstance(url, str):
            return ""
        try:
            parsed = urlparse(url.strip())
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            path = parsed.path
            if path != "/" and path.endswith("/"):
                path = path.rstrip("/")

            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=True)
                if strip_tracking:
                    params = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
                sorted_query = urlencode(sorted(params.items()), doseq=True)
            else:
                sorted_query = ""

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
