"""
Social media profile discovery from website HTML, footer, header, JSON-LD, and sameAs tags.
Supports LinkedIn, X/Twitter, Instagram, Facebook, YouTube, GitHub, Threads, Pinterest, Telegram, Medium, Substack.
"""
import re
import json
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PLATFORM_PATTERNS = {
    "linkedin": [
        r"https?:\/\/(?:[a-zA-Z0-9\-_]+\.)?linkedin\.com\/in\/([a-zA-Z0-9_\-\.]+)",
        r"https?:\/\/(?:[a-zA-Z0-9\-_]+\.)?linkedin\.com\/pub\/([a-zA-Z0-9_\-\.]+)",
        r"https?:\/\/(?:[a-zA-Z0-9\-_]+\.)?linkedin\.com\/(?:company|school)\/([a-zA-Z0-9_\-\.]+)",
    ],
    "twitter": [
        r"https?:\/\/(?:www\.)?(?:twitter|x)\.com\/([a-zA-Z0-9_]{1,30})",
    ],
    "instagram": [
        r"https?:\/\/(?:www\.)?instagram\.com\/([a-zA-Z0-9_\.]+)",
    ],
    "facebook": [
        r"https?:\/\/(?:www\.)?facebook\.com\/(?:people\/[^\/]+\/([0-9]+)|([a-zA-Z0-9_\.\-]+))",
    ],
    "youtube": [
        r"https?:\/\/(?:www\.)?youtube\.com\/@([a-zA-Z0-9_\-\.]+)",
        r"https?:\/\/(?:www\.)?youtube\.com\/(?:c\/|channel\/|user\/)([a-zA-Z0-9_\-\.]+)",
    ],
    "github": [
        r"https?:\/\/(?:www\.)?github\.com\/([a-zA-Z0-9_\-]+)",
    ],
    "threads": [
        r"https?:\/\/(?:www\.)?threads\.net\/@?([a-zA-Z0-9_\.]+)",
    ],
    "pinterest": [
        r"https?:\/\/(?:www\.)?pinterest\.(?:com|[a-z]{2}|co\.[a-z]{2})\/([a-zA-Z0-9_\-]+)",
    ],
    "telegram": [
        r"https?:\/\/(?:t|telegram)\.me\/([a-zA-Z0-9_]{4,})",
    ],
    "medium": [
        r"https?:\/\/(?:www\.)?medium\.com\/@([a-zA-Z0-9_\.\-]+)",
        r"https?:\/\/([a-zA-Z0-9_\-]+)\.medium\.com",
    ],
    "substack": [
        r"https?:\/\/([a-zA-Z0-9_\-]+)\.substack\.com",
    ],
}

IGNORED_HANDLES = {
    "share", "intent", "sharer", "home", "about", "terms", "privacy", "help",
    "login", "signup", "search", "policies", "explore", "p", "reel", "reels",
    "stories", "tags", "hashtag", "watch", "feed", "posts", "wiki", "settings",
    "notifications", "groups", "pages", "events", "hashtag", "i", "widgets"
}


class SocialDiscovery:
    def discover_from_html(self, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract and categorize social media links with verification tags and normalized handles."""
        if not html:
            return []

        results: List[Dict[str, Any]] = []
        seen_urls = set()

        soup = BeautifulSoup(html, "html.parser")

        # 1. JSON-LD schema sameAs tags (high confidence)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text() or "{}")
                same_as_list = []
                if isinstance(data, dict):
                    sa = data.get("sameAs", [])
                    same_as_list = [sa] if isinstance(sa, str) else (sa if isinstance(sa, list) else [])
                    # Also check nested Person/Org
                    for sub_key in ("author", "creator", "publisher", "mainEntity"):
                        sub_obj = data.get(sub_key)
                        if isinstance(sub_obj, dict) and "sameAs" in sub_obj:
                            s = sub_obj["sameAs"]
                            same_as_list.extend([s] if isinstance(s, str) else (s if isinstance(s, list) else []))
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
                                "confidence": 0.95,
                            })
            except Exception:
                pass

        # 2. Anchor tags throughout page (including footer, header, infobox, body)
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            match = self._classify_url(href)
            if match and match["url"] not in seen_urls:
                seen_urls.add(match["url"])
                parent_tag = a.find_parent(["footer", "nav", "header", "table", "aside"])
                parent_classes = " ".join(parent_tag.get("class", [])) if parent_tag and parent_tag.get("class") else ""
                
                # Check for infobox or official section
                is_infobox = "infobox" in parent_classes or "vcard" in parent_classes or "profile" in parent_classes
                if is_infobox:
                    status = "likely_official"
                    conf = 0.90
                    method = "anchor_infobox"
                elif parent_tag and parent_tag.name in ["footer", "header"]:
                    status = "likely_official"
                    conf = 0.85
                    method = f"anchor_{parent_tag.name}"
                else:
                    status = "unverified"
                    conf = 0.70
                    method = "anchor_body"

                results.append({
                    **match,
                    "source_url": source_url,
                    "extraction_method": method,
                    "verification_status": status,
                    "confidence": conf,
                })

        return results

    def _classify_url(self, raw_url: str) -> Optional[Dict[str, str]]:
        if not raw_url or not isinstance(raw_url, str):
            return None

        # Clean tracking parameters, fragments, whitespace
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            return None

        try:
            parsed = urlparse(url)
            clean_netloc = parsed.netloc.lower()
            clean_path = parsed.path.rstrip("/")
            # Standardize scheme to https
            normalized_url = urlunparse(("https", clean_netloc, clean_path, "", "", ""))
        except Exception:
            normalized_url = url.split("?")[0].split("#")[0].rstrip("/")

        for platform, patterns in PLATFORM_PATTERNS.items():
            for pat in patterns:
                m = re.match(pat, normalized_url, re.IGNORECASE)
                if m:
                    # Capture handle group (handle could be in group 1 or group 2)
                    handle = None
                    for g in m.groups():
                        if g:
                            handle = g.lower().strip("@/")
                            break
                    if not handle or handle in IGNORED_HANDLES:
                        continue
                    return {
                        "platform": platform,
                        "url": normalized_url,
                        "handle": handle,
                    }
        return None
