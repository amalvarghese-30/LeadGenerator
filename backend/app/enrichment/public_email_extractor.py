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
OBFUSCATED_EMAIL_REGEX = re.compile(
    r'\b([A-Za-z0-9._%+-]+)\s*(?:\[at\]|\(at\)|\bat\b)\s*([A-Za-z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\bdot\b|\.)\s*([A-Za-z]{2,7})\b',
    re.IGNORECASE
)

BLOCKED_EMAIL_DOMAINS = {
    "sentry.io", "wixpress.com", "example.com", "test.com", "schema.org",
    "cloudflare.com", "googleapis.com", "w3.org", "domain.com", "email.com",
    "mycompany.com", "yourcompany.com", "placeholder.com"
}

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

        def _is_blocked(email_str: str) -> bool:
            if not email_str or "@" not in email_str:
                return True
            domain = email_str.split("@")[-1].lower()
            return domain in BLOCKED_EMAIL_DOMAINS or any(domain.endswith("." + bd) for bd in BLOCKED_EMAIL_DOMAINS)

        # 1. Mailto links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_mail = unquote(href[7:].split("?")[0].strip())
                if raw_mail and "@" in raw_mail:
                    clean_mail = raw_mail.lower().strip()
                    if clean_mail not in seen_emails and not clean_mail.endswith((".png", ".jpg", ".webp")) and not _is_blocked(clean_mail):
                        seen_emails.add(clean_mail)
                        quote = a.get_text(strip=True) or (a.parent.get_text(strip=True)[:150] if a.parent else "")
                        scope = PublicEmailExtractor.classify_scope(clean_mail, target_person_name)
                        results.append(ExtractedEmail(
                            value=clean_mail,
                            scope=scope,
                            source_url=source_url,
                            source_type="mailto",
                            evidence_quote=f"Mailto anchor: '{quote}'",
                            confidence=0.9 if scope == "person_direct_work" else 0.8,
                        ))

        # 2. Explicit inspection of header, nav, footer, and address blocks
        for container in soup.find_all(["header", "nav", "footer", "address"]):
            c_name = container.name
            c_text = container.get_text(separator=" ", strip=True)
            for m in EMAIL_REGEX.findall(c_text):
                clean_mail = m.lower().strip().rstrip(".,;:)")
                if not clean_mail or clean_mail in seen_emails or _is_blocked(clean_mail):
                    continue
                if clean_mail.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".pdf", ".css", ".js")):
                    continue
                seen_emails.add(clean_mail)
                scope = PublicEmailExtractor.classify_scope(clean_mail, target_person_name)
                results.append(ExtractedEmail(
                    value=clean_mail,
                    scope=scope,
                    source_url=source_url,
                    source_type=f"webpage_{c_name}",
                    evidence_quote=f"Extracted from <{c_name}>: '{clean_mail}'",
                    confidence=0.85 if scope == "person_direct_work" else 0.8,
                ))

        # 3. Visible text emails across full page
        text = soup.get_text(separator=" ", strip=True)
        raw_matches = EMAIL_REGEX.findall(text)
        for m in raw_matches:
            clean_mail = m.lower().strip().rstrip(".,;:)")
            if not clean_mail or clean_mail in seen_emails or _is_blocked(clean_mail):
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
                confidence=0.8 if scope == "person_direct_work" else 0.7,
            ))

        # 4. Obfuscated emails (e.g. user [at] example [dot] com)
        for m in OBFUSCATED_EMAIL_REGEX.finditer(text):
            reconstructed = f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower().strip()
            if reconstructed not in seen_emails and not reconstructed.endswith((".png", ".jpg", ".webp")) and not _is_blocked(reconstructed):
                seen_emails.add(reconstructed)
                raw_match_text = m.group(0)
                scope = PublicEmailExtractor.classify_scope(reconstructed, target_person_name)
                results.append(ExtractedEmail(
                    value=reconstructed,
                    scope=scope,
                    source_url=source_url,
                    source_type="obfuscated_text",
                    evidence_quote=f"De-obfuscated from '{raw_match_text}'",
                    confidence=0.75 if scope == "person_direct_work" else 0.65,
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
