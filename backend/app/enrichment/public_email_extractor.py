"""
Public Business Email Extractor: Extracts and classifies explicitly published
business email addresses with source evidence and strict pattern anti-hallucination.
"""
import re
from typing import List, Dict, Optional, Any
from urllib.parse import unquote
from pydantic import BaseModel
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

GENERIC_LOCAL_PARTS = {
    "info", "contact", "hello", "office", "enquiry", "enquiries",
    "general", "mail", "admin", "welcome", "inbox", "team"
}

DEPARTMENT_LOCAL_PARTS = {
    "support", "help", "helpdesk", "care", "service", "customerservice",
    "billing", "accounts", "finance", "careers", "jobs", "hr", "recruitment", "talent"
}

SALES_LOCAL_PARTS = {
    "sales", "business", "growth", "partners", "partnerships", "deals", "consulting"
}

MEDIA_LOCAL_PARTS = {
    "press", "media", "pr", "news", "communications"
}


class ExtractedEmail(BaseModel):
    value: str
    scope: str  # person_direct_work | company_generic | department | media_enquiry | sales_enquiry | unclassified
    source_url: str
    source_type: str = "webpage"  # webpage | mailto | json_ld_person | json_ld_org | json_ld_contactpoint
    evidence_quote: Optional[str] = None
    confidence: float = 0.5


class PublicEmailExtractor:
    @staticmethod
    def extract_from_html(
        html: str,
        source_url: str,
        target_person_name: Optional[str] = None,
        target_company_name: Optional[str] = None,
    ) -> List[ExtractedEmail]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results: List[ExtractedEmail] = []
        seen_emails = set()

        # 1. Mailto links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_mail = unquote(href[7:].split("?")[0].strip())
                if raw_mail and "@" in raw_mail:
                    clean_mail = raw_mail.lower().strip()
                    if clean_mail not in seen_emails and not clean_mail.endswith((".png", ".jpg", ".webp")):
                        seen_emails.add(clean_mail)
                        quote = a.get_text(strip=True) or a.parent.get_text(strip=True)[:150]
                        scope = PublicEmailExtractor.classify_scope(clean_mail, target_person_name)
                        results.append(ExtractedEmail(
                            value=clean_mail,
                            scope=scope,
                            source_url=source_url,
                            source_type="mailto",
                            evidence_quote=f"Mailto anchor: '{quote}'",
                            confidence=0.85 if scope == "person_direct_work" else 0.7,
                        ))

        # 2. Visible text emails
        text = soup.get_text(separator=" ", strip=True)
        raw_matches = EMAIL_REGEX.findall(text)
        for m in raw_matches:
            clean_mail = m.lower().strip().rstrip(".,;:)")
            if not clean_mail or clean_mail in seen_emails:
                continue
            if clean_mail.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".pdf", ".css", ".js")):
                continue
            seen_emails.add(clean_mail)

            # Find context quote around the email
            pos = text.lower().find(clean_mail)
            start = max(0, pos - 80)
            end = min(len(text), pos + len(clean_mail) + 80)
            evidence = text[start:end].strip()

            scope = PublicEmailExtractor.classify_scope(clean_mail, target_person_name)
            results.append(ExtractedEmail(
                value=clean_mail,
                scope=scope,
                source_url=source_url,
                source_type="webpage",
                evidence_quote=f"...{evidence}...",
                confidence=0.8 if scope == "person_direct_work" else 0.65,
            ))

        return results

    @staticmethod
    def classify_scope(email: str, target_person_name: Optional[str] = None) -> str:
        local_part = email.split("@")[0].lower()

        # Check generic / department / sales / media local parts first
        if local_part in GENERIC_LOCAL_PARTS:
            return "company_generic"
        if local_part in DEPARTMENT_LOCAL_PARTS:
            return "department"
        if local_part in SALES_LOCAL_PARTS:
            return "sales_enquiry"
        if local_part in MEDIA_LOCAL_PARTS:
            return "media_enquiry"

        # Check if local part matches person's name tokens
        if target_person_name:
            tokens = [t.lower() for t in target_person_name.split() if len(t) > 2]
            if tokens:
                # E.g. john@, john.doe@, jdoe@, doe.john@
                first = tokens[0]
                last = tokens[-1] if len(tokens) > 1 else ""
                if first in local_part or (last and last in local_part):
                    return "person_direct_work"
                if last and f"{first[0]}{last}" in local_part:
                    return "person_direct_work"

        # If it doesn't match generic and has distinct name-like structure, could be direct or unclassified
        if "." in local_part or "_" in local_part:
            return "person_direct_work" if target_person_name else "unclassified"

        return "unclassified"
