"""
Content extraction using Trafilatura and BeautifulSoup.
Extracts clean main text, Schema.org Person/Organization structures,
JSON-LD data, social profiles, and legitimate publicly published contact channels.
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import trafilatura

from app.discovery.social_discovery import SocialDiscovery

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')

class ContentExtractor:
    def __init__(self):
        self.social_discovery = SocialDiscovery()

    def extract(self, html: str, url: str) -> Dict[str, Any]:
        """Extract structured content and metadata from webpage HTML."""
        if not html:
            return {
                "url": url,
                "title": "",
                "meta_description": "",
                "main_text": "",
                "word_count": 0,
                "json_ld": [],
                "schema_persons": [],
                "schema_organizations": [],
                "social_profiles": [],
                "public_emails": [],
                "public_phones": [],
                "contact_forms": [],
            }

        soup = BeautifulSoup(html, "html.parser")

        # 1. Title & Meta
        title = ""
        title_el = soup.find("title")
        if title_el and title_el.text:
            title = title_el.text.strip()

        meta_desc = ""
        meta_el = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta_el and meta_el.get("content"):
            meta_desc = meta_el["content"].strip()

        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
        h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2")][:10]

        # 2. Clean main text using Trafilatura
        extracted_text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        ) or ""

        # Fallback to BeautifulSoup if Trafilatura returns empty
        if not extracted_text:
            # Remove scripts & styles
            for elem in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
                elem.decompose()
            extracted_text = soup.get_text(separator="\n", strip=True)

        # Cap text length to prevent memory saturation
        capped_text = extracted_text[:40000]

        # 3. JSON-LD parsing
        json_ld_list: List[Dict[str, Any]] = []
        schema_persons: List[Dict[str, Any]] = []
        schema_orgs: List[Dict[str, Any]] = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        json_ld_list.append(item)
                        item_type = str(item.get("@type", "")).lower()
                        if "person" in item_type:
                            schema_persons.append({
                                "name": item.get("name"),
                                "job_title": item.get("jobTitle"),
                                "works_for": item.get("worksFor", {}).get("name") if isinstance(item.get("worksFor"), dict) else item.get("worksFor"),
                                "url": item.get("url"),
                                "same_as": item.get("sameAs", []),
                            })
                        elif any(k in item_type for k in ["organization", "corporation", "localbusiness"]):
                            schema_orgs.append({
                                "name": item.get("name"),
                                "url": item.get("url"),
                                "email": item.get("email"),
                                "telephone": item.get("telephone"),
                                "same_as": item.get("sameAs", []),
                            })
            except Exception:
                pass

        # 4. Social profiles
        social_profiles = self.social_discovery.discover_from_html(html, url)

        # 5. Publicly published business contact channels
        # Strictly regex on public business text
        found_emails = list(set(EMAIL_REGEX.findall(capped_text)))
        # Filter obvious static asset false positives
        valid_emails = [e for e in found_emails if not e.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"))]

        # Contact forms
        contact_forms = []
        for form in soup.find_all("form"):
            action = form.get("action", "")
            if any(k in action.lower() or k in str(form).lower() for k in ["contact", "enquiry", "message", "support"]):
                contact_forms.append(action or url)

        return {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "h1": h1_tags[0] if h1_tags else "",
            "h2s": h2_tags,
            "main_text": capped_text,
            "word_count": len(capped_text.split()),
            "json_ld": json_ld_list,
            "schema_persons": schema_persons,
            "schema_organizations": schema_orgs,
            "social_profiles": social_profiles,
            "public_emails": valid_emails,
            "contact_forms": list(set(contact_forms)),
        }
