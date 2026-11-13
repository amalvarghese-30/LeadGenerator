"""
Contact Page Discovery: Discovers dedicated contact, leadership, about, and team pages
from a target website's HTML, internal links, headers, footers, and standard paths.
"""
import re
from typing import List, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

TARGET_PATH_KEYWORDS = [
    "contact", "contact-us", "contactus", "get-in-touch",
    "about", "about-us", "aboutus", "our-story",
    "team", "our-team", "leadership", "management", "executives", "people", "board",
    "company", "profile", "press", "media", "speaking", "author", "bio"
]

COMMON_PATHS = [
    "/contact", "/contact-us", "/about", "/about-us",
    "/team", "/our-team", "/leadership", "/management",
    "/company", "/press", "/media"
]


class ContactPageDiscovery:
    @staticmethod
    def discover_pages_from_html(html: str, base_url: str) -> List[str]:
        """Extract prioritized contact & about page URLs from page HTML."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower()

        candidate_urls: Set[str] = set()

        # Prioritize footer and header links
        for container in soup.find_all(["footer", "nav", "header"]):
            for a in container.find_all("a", href=True):
                href = a["href"].strip()
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                if parsed.netloc.lower() == base_domain:
                    path = parsed.path.lower()
                    link_text = a.get_text(strip=True).lower()
                    if any(kw in path or kw in link_text for kw in TARGET_PATH_KEYWORDS):
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        candidate_urls.add(clean_url)

        # Body links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc.lower() == base_domain:
                path = parsed.path.lower()
                link_text = a.get_text(strip=True).lower()
                if any(kw in path for kw in TARGET_PATH_KEYWORDS) or any(kw in link_text for kw in ["contact us", "get in touch", "our leadership", "our team"]):
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    candidate_urls.add(clean_url)

        # Sort with contact and team first
        def _priority_score(u: str) -> int:
            u_low = u.lower()
            if "contact" in u_low:
                return 0
            if "team" in u_low or "leadership" in u_low:
                return 1
            if "about" in u_low:
                return 2
            return 3

        sorted_pages = sorted(list(candidate_urls), key=_priority_score)
        return sorted_pages[:8]

    @staticmethod
    def get_standard_candidate_urls(base_url: str) -> List[str]:
        """Generate canonical target contact paths on the domain."""
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        return [f"{root}{p}" for p in COMMON_PATHS]
