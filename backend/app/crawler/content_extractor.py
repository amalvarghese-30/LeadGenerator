"""
Content extraction using Trafilatura, BeautifulSoup, and phonenumbers.
Extracts clean main text, Schema.org Person/Organization structures,
JSON-LD data (@graph, Person, Organization, ContactPoint), social profiles,
and legitimate publicly published contact channels (emails, phones, contact forms).
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import unquote
from bs4 import BeautifulSoup
import trafilatura
import phonenumbers

from app.discovery.social_discovery import SocialDiscovery

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
OBFUSCATED_EMAIL_REGEX = re.compile(
    r'\b([A-Za-z0-9._%+-]+)\s*(?:\[at\]|\(at\)|\bat\b)\s*([A-Za-z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\bdot\b|\.)\s*([A-Za-z]{2,7})\b',
    re.IGNORECASE
)
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
            clone_soup = BeautifulSoup(html, "html.parser")
            for elem in clone_soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
                elem.decompose()
            extracted_text = clone_soup.get_text(separator="\n", strip=True)

        capped_text = extracted_text[:40000]

        # 3. JSON-LD parsing (recursively handles @graph, Person, Organization, ContactPoint)
        json_ld_list: List[Dict[str, Any]] = []
        schema_persons: List[Dict[str, Any]] = []
        schema_orgs: List[Dict[str, Any]] = []
        schema_emails: List[str] = []
        schema_phones: List[str] = []

        def _process_json_ld_item(item: Any):
            if not isinstance(item, dict):
                return
            json_ld_list.append(item)

            # Check @graph arrays
            if "@graph" in item and isinstance(item["@graph"], list):
                for sub in item["@graph"]:
                    _process_json_ld_item(sub)

            raw_type = item.get("@type", "")
            types = [raw_type.lower()] if isinstance(raw_type, str) else [str(t).lower() for t in raw_type]

            # Person schema
            if any("person" in t for t in types):
                email = item.get("email")
                phone = item.get("telephone")
                if email and isinstance(email, str):
                    schema_emails.append(email.strip())
                if phone and isinstance(phone, str):
                    schema_phones.append(phone.strip())

                schema_persons.append({
                    "name": item.get("name"),
                    "job_title": item.get("jobTitle"),
                    "works_for": item.get("worksFor", {}).get("name") if isinstance(item.get("worksFor"), dict) else item.get("worksFor"),
                    "email": email if isinstance(email, str) else None,
                    "telephone": phone if isinstance(phone, str) else None,
                    "url": item.get("url"),
                    "same_as": item.get("sameAs", []),
                })

            # Organization schema
            elif any(k in t for t in types for k in ["organization", "corporation", "localbusiness", "educationalorganization"]):
                email = item.get("email")
                phone = item.get("telephone")
                if email and isinstance(email, str):
                    schema_emails.append(email.strip())
                if phone and isinstance(phone, str):
                    schema_phones.append(phone.strip())

                # Inspect nested contactPoint
                contact_points = item.get("contactPoint", [])
                if isinstance(contact_points, dict):
                    contact_points = [contact_points]
                cp_list = []
                if isinstance(contact_points, list):
                    for cp in contact_points:
                        if isinstance(cp, dict):
                            cp_email = cp.get("email")
                            cp_tel = cp.get("telephone")
                            if cp_email and isinstance(cp_email, str):
                                schema_emails.append(cp_email.strip())
                            if cp_tel and isinstance(cp_tel, str):
                                schema_phones.append(cp_tel.strip())
                            cp_list.append({
                                "telephone": cp_tel,
                                "email": cp_email,
                                "contact_type": cp.get("contactType"),
                                "area_served": cp.get("areaServed"),
                            })

                schema_orgs.append({
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "email": email if isinstance(email, str) else None,
                    "telephone": phone if isinstance(phone, str) else None,
                    "contact_points": cp_list,
                    "same_as": item.get("sameAs", []),
                })

            # Independent ContactPoint
            elif any("contactpoint" in t for t in types):
                cp_email = item.get("email")
                cp_tel = item.get("telephone")
                if cp_email and isinstance(cp_email, str):
                    schema_emails.append(cp_email.strip())
                if cp_tel and isinstance(cp_tel, str):
                    schema_phones.append(cp_tel.strip())

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw_text = script.string or script.get_text() or "{}"
                data = json.loads(raw_text)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    _process_json_ld_item(item)
            except Exception:
                pass

        # 4. Social profiles
        social_profiles = self.social_discovery.discover_from_html(html, url)

        # 5. Mailto & Tel DOM links
        mailto_emails: List[str] = []
        tel_phones: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                clean_email = href[7:].split("?")[0].strip()
                clean_email = unquote(clean_email)
                if clean_email and "@" in clean_email:
                    mailto_emails.append(clean_email)
            elif href.lower().startswith("tel:"):
                clean_phone = href[4:].split("?")[0].strip()
                clean_phone = unquote(clean_phone)
                if clean_phone:
                    tel_phones.append(clean_phone)

        # 6. Publicly published business emails
        raw_text_emails = EMAIL_REGEX.findall(capped_text)
        obfuscated_emails = []
        for m in OBFUSCATED_EMAIL_REGEX.finditer(capped_text):
            obfuscated_emails.append(f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower().strip())
        all_candidate_emails = list(set(raw_text_emails + obfuscated_emails + mailto_emails + schema_emails))
        valid_emails = []
        for e in all_candidate_emails:
            e_clean = e.strip().rstrip(".,;:)")
            if not e_clean or "@" not in e_clean:
                continue
            if e_clean.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".pdf", ".css", ".js")):
                continue
            valid_emails.append(e_clean)
        valid_emails = list(dict.fromkeys(valid_emails))

        # 7. Publicly published business phones (phonenumbers parsing + tel links)
        raw_text_phone_candidates = PHONE_REGEX.findall(capped_text)
        all_candidate_phones = list(set(tel_phones + schema_phones + raw_text_phone_candidates))
        valid_phones = []

        for p_raw in all_candidate_phones:
            p_clean = p_raw.strip().strip(".,;:()")
            if len(re.sub(r'\D', '', p_clean)) < 7:
                continue
            try:
                parsed = phonenumbers.parse(p_clean, "IN")
                if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    valid_phones.append(formatted)
                elif phonenumbers.is_possible_number(parsed):
                    # Valid length and national format
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    valid_phones.append(formatted)
            except Exception:
                # If phonenumbers cannot parse it but it came from a tel: link or schema, retain clean digits
                if p_raw in tel_phones or p_raw in schema_phones:
                    clean_digits = re.sub(r'[^\d+]', '', p_clean)
                    if len(clean_digits) >= 8:
                        valid_phones.append(clean_digits)

        valid_phones = list(dict.fromkeys(valid_phones))

        # 8. Contact forms
        contact_forms = []
        for form in soup.find_all("form"):
            action = form.get("action", "")
            form_str = str(form).lower()
            if any(k in action.lower() or k in form_str for k in ["contact", "enquiry", "message", "support", "get-in-touch"]):
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
            "public_phones": valid_phones,
            "contact_forms": list(set(contact_forms)),
        }
