"""
Public Business Phone Extractor: Parses, validates, and normalizes international
and Indian phone numbers using phonenumbers into E.164 standard format.
Classifies phone numbers into direct vs switchboard vs department vs public enquiry.
"""
import re
from typing import List, Optional, Dict, Any
from urllib.parse import unquote
import phonenumbers
from bs4 import BeautifulSoup
from pydantic import BaseModel

PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')


class ExtractedPhone(BaseModel):
    value: str  # E.164 format (e.g. +919876543210)
    original_text: str
    scope: str  # person_direct_work | company_switchboard | department | public_business_enquiry | unclassified
    source_url: str
    source_type: str = "webpage"  # webpage | tel | json_ld_org | json_ld_person | json_ld_contactpoint
    evidence_quote: Optional[str] = None
    country_code: Optional[int] = None
    confidence: float = 0.5


class PublicPhoneExtractor:
    @staticmethod
    def extract_from_html(
        html: str,
        source_url: str,
        target_person_name: Optional[str] = None,
        default_region: str = "IN",
    ) -> List[ExtractedPhone]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results: List[ExtractedPhone] = []
        seen_numbers = set()

        # 1. Tel: links in DOM
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("tel:"):
                raw_tel = unquote(href[4:].split("?")[0].strip())
                parsed = PublicPhoneExtractor._parse_and_format(raw_tel, default_region)
                if parsed and parsed["e164"] not in seen_numbers:
                    seen_numbers.add(parsed["e164"])
                    anchor_text = a.get_text(strip=True) or a.parent.get_text(strip=True)[:100]
                    scope = PublicPhoneExtractor.classify_scope(anchor_text, target_person_name)
                    results.append(ExtractedPhone(
                        value=parsed["e164"],
                        original_text=raw_tel,
                        scope=scope,
                        source_url=source_url,
                        source_type="tel",
                        evidence_quote=f"Tel link: '{anchor_text}'",
                        country_code=parsed.get("country_code"),
                        confidence=0.85 if scope == "person_direct_work" else 0.7,
                    ))

        # 2. Text matches
        text = soup.get_text(separator=" ", strip=True)
        raw_matches = PHONE_REGEX.findall(text)
        for raw in raw_matches:
            clean = raw.strip().strip(".,;:()")
            if len(re.sub(r'\D', '', clean)) < 7:
                continue

            parsed = PublicPhoneExtractor._parse_and_format(clean, default_region)
            if parsed and parsed["e164"] not in seen_numbers:
                seen_numbers.add(parsed["e164"])

                pos = text.find(raw)
                start = max(0, pos - 60)
                end = min(len(text), pos + len(raw) + 60)
                context = text[start:end].strip()

                scope = PublicPhoneExtractor.classify_scope(context, target_person_name)
                results.append(ExtractedPhone(
                    value=parsed["e164"],
                    original_text=clean,
                    scope=scope,
                    source_url=source_url,
                    source_type="webpage",
                    evidence_quote=f"...{context}...",
                    country_code=parsed.get("country_code"),
                    confidence=0.75 if scope == "person_direct_work" else 0.6,
                ))

        return results

    @staticmethod
    def _parse_and_format(raw: str, default_region: str = "IN") -> Optional[Dict[str, Any]]:
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                return {
                    "e164": e164,
                    "country_code": parsed.country_code,
                }
        except Exception:
            pass
        return None

    @staticmethod
    def classify_scope(context: str, target_person_name: Optional[str] = None) -> str:
        ctx_low = context.lower()

        # Check for direct person cues
        if target_person_name:
            first_name = target_person_name.split()[0].lower()
            if first_name in ctx_low and any(w in ctx_low for w in ["direct", "mobile", "cell", "personal"]):
                return "person_direct_work"

        if any(w in ctx_low for w in ["direct line", "mobile:", "mob:", "cell:"]):
            return "person_direct_work"

        if any(w in ctx_low for w in ["switchboard", "board:", "reception", "office:", "hq:", "headquarters", "main line"]):
            return "company_switchboard"

        if any(w in ctx_low for w in ["sales:", "sales enquiry", "support:", "customer care", "helpdesk"]):
            return "department"

        if any(w in ctx_low for w in ["enquiry", "call us", "contact us", "toll free", "tollfree"]):
            return "public_business_enquiry"

        return "company_switchboard"  # Default assumption for company websites: belongs to company, not individual
