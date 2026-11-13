"""
Social media profile discovery from website HTML, footer, header, JSON-LD, and sameAs tags.
Supports LinkedIn, Instagram, Facebook, YouTube, and X (Twitter).
"""
import re
import json
import logging
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PLATFORM_PATTERNS = {
    "linkedin": [
        r"https?:\/\/(?:www\.)?linkedin\.com\/(?:company|school)\/([a-zA-Z0-9_\-\.]+)",
        r"https?:\/\/(?:www\.)?linkedin\.com\/in\/([a-zA-Z0-9_\-\.]+)",
    ],
    "twitter": [
        r"https?:\/\/(?:www\.)?(?:twitter|x)\.com\/([a-zA-Z0-9_]{1,15})",
    ],
    "instagram": [
        r"https?:\/\/(?:www\.)?instagram\.com\/([a-zA-Z0-9_\.]+)",
    ],
    "facebook": [
        r"https?:\/\/(?:www\.)?facebook\.com\/([a-zA-Z0-9_\.\-]+)",
    ],
    "youtube": [
        r"https?:\/\/(?:www\.)?youtube\.com\/(?:@|c\/|channel\/|user\/)([a-zA-Z0-9_\-]+)",
    ],
}

IGNORED_HANDLES = {
    "share", "intent", "sharer", "home", "about", "terms", "privacy", "help",
    "login", "signup", "search", "policies", "explore"
}

class SocialDiscovery:
    def discover_from_html(self, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract and categorize social media links with verification tags."""
        if not html:
            return []

        results: List[Dict[str, Any]] = []
        seen_urls = set()

        soup = BeautifulSoup(html, "html.parser")

        # 1. JSON-LD schema sameAs tags (often high confidence)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                same_as_list = []
                if isinstance(data, dict):
                    sa = data.get("sameAs", [])
                    same_as_list = [sa] if isinstance(sa, str) else (sa if isinstance(sa, list) else [])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "sameAs" in item:
                            sa = item.get("sameAs")
                            same_as_list.extend([sa] if isinstance(sa, str) else (sa if isinstance(sa, list) else []))

                for url in same_as_list:
                    if isinstance(url, str):
                        match = self._classify_url(url)
                        if match and match["url"] not in seen_urls:
                            seen_urls.add(match["url"])
                            results.append({
                                **match,
                                "source_url": source_url,
                                "extraction_method": "json_ld_sameAs",
                                "verification_status": "likely_official",
                            })
            except Exception:
                pass

        # 2. Anchor tags throughout page
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            match = self._classify_url(href)
            if match and match["url"] not in seen_urls:
                seen_urls.add(match["url"])
                # Check if located in footer or header for higher confidence
                parent_tag = a.find_parent(["footer", "nav", "header"])
                status = "likely_official" if parent_tag else "unverified"
                results.append({
                    **match,
                    "source_url": source_url,
                    "extraction_method": f"anchor_{parent_tag.name if parent_tag else 'body'}",
                    "verification_status": status,
                })

        return results

    def _classify_url(self, url: str) -> Optional[Dict[str, str]]:
        if not url or not url.startswith("http"):
            return None

        clean_url = url.split("?")[0].rstrip("/")
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pat in patterns:
                m = re.match(pat, clean_url, re.IGNORECASE)
                if m:
                    handle = m.group(1).lower()
                    if handle in IGNORED_HANDLES:
                        continue
                    return {
                        "platform": platform,
                        "url": clean_url,
                        "handle": handle,
                    }
        return None
