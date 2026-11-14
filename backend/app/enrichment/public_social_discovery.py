"""
Public Social Media & Community Forum Discovery
Discovers publicly available contact channels (emails, phones, verified profiles)
from social media platforms (LinkedIn, Twitter/X, Instagram, GitHub),
corporate registries (TheCompanyCheck, ZaubaCorp), forums, and public bio snippets.
"""
import re
import time
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from app.discovery.ddgs_search import DDGSSearch
from app.enrichment.public_email_extractor import EMAIL_REGEX
import phonenumbers

logger = logging.getLogger(__name__)

SOCIAL_PLATFORMS = {
    "linkedin.com/in/": "linkedin",
    "linkedin.com/pub/": "linkedin",
    "twitter.com/": "twitter",
    "x.com/": "twitter",
    "instagram.com/": "instagram",
    "github.com/": "github",
    "youtube.com/": "youtube",
    "medium.com/": "medium",
    "substack.com": "substack",
}

class PublicSocialDiscovery:
    def __init__(self):
        self.searcher = DDGSSearch(max_results=5)

    def search_social_and_forums(
        self,
        full_name: str,
        company_name: Optional[str] = None,
        designation: Optional[str] = None,
        existing_socials: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs non-intrusive public queries to discover contact details
        from social media profiles, public registries, and discussion forums.
        """
        if not full_name:
            return []

        existing_socials = existing_socials or {}
        discovered_channels: List[Dict[str, Any]] = []
        clean_comp = re.sub(r'[^a-zA-Z0-9\s]', '', company_name or "").strip()

        queries = [
            f"{full_name} {clean_comp} contact email",
            f"{full_name} {clean_comp} phone OR mobile",
            f"site:linkedin.com/in/ {full_name} {clean_comp}",
            f"site:thecompanycheck.com {full_name}",
        ]

        seen_values = set()

        for q in queries:
            try:
                results = self.searcher.search(q, region="in-en")
                for r in results:
                    title = r.get("title", "")
                    snippet = r.get("body", "") or r.get("snippet", "")
                    url = r.get("url") or r.get("href", "")
                    combined_text = f"{title} {snippet}"

                    # 1. Check for Social Profiles
                    for pattern, platform in SOCIAL_PLATFORMS.items():
                        if pattern in url.lower():
                            if url not in seen_values and url not in existing_socials.values():
                                seen_values.add(url)
                                discovered_channels.append({
                                    "type": "social",
                                    "scope": "person_direct_work",
                                    "value": url,
                                    "source_url": url,
                                    "source_type": f"{platform}_profile",
                                    "evidence_quote": f"Discovered public {platform} profile: {title}",
                                    "is_official": True,
                                    "confidence": 0.85,
                                    "verification_status": "source_verified",
                                })

                    # 2. Extract Publicly Published Emails from snippet/title
                    emails = EMAIL_REGEX.findall(combined_text)
                    for em in emails:
                        em_clean = em.lower().strip(".")
                        # Ignore generic site emails from search engines
                        if any(d in em_clean for d in ["duckduckgo.com", "example.com", "sentry.io"]):
                            continue
                        if em_clean not in seen_values:
                            seen_values.add(em_clean)
                            discovered_channels.append({
                                "type": "email",
                                "scope": "person_direct_work" if (full_name.split()[0].lower() in em_clean or "@gmail.com" in em_clean) else "company_generic",
                                "value": em_clean,
                                "source_url": url,
                                "source_type": "public_search_snippet",
                                "evidence_quote": f"Public email published in snippet: {snippet[:120]}",
                                "is_official": True,
                                "confidence": 0.8,
                                "verification_status": "published",
                            })

                    # 3. Extract Publicly Published Phone Numbers from snippet/title
                    for match in phonenumbers.PhoneNumberMatcher(combined_text, "IN"):
                        num = match.number
                        if phonenumbers.is_possible_number(num) and phonenumbers.is_valid_number(num):
                            ph = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
                            if ph not in seen_values:
                                seen_values.add(ph)
                                discovered_channels.append({
                                    "type": "phone",
                                    "scope": "person_direct_work",
                                    "value": ph,
                                    "source_url": url,
                                    "source_type": "public_search_snippet",
                                    "evidence_quote": f"Public phone published in snippet: {snippet[:120]}",
                                    "is_official": True,
                                    "confidence": 0.75,
                                    "verification_status": "published",
                                })
            except Exception as e:
                logger.debug("Social search failed for query %s: %s", q, e)
                continue
            finally:
                time.sleep(1.0)

        return discovered_channels
