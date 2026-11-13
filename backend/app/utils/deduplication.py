import hashlib
import re
import unicodedata
from typing import Optional


def _normalize_string(s: str) -> str:
    """Lowercase, strip accents, remove punctuation/whitespace."""
    if not s:
        return ""
    # Unicode normalize
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Remove non-alphanumeric
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def generate_contact_dedup_key(
    full_name: str,
    email: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    company_name: Optional[str] = None,
) -> str:
    """
    Generate a deduplication key for a contact.
    Priority: email > linkedin_url > name+company hash
    """
    if email:
        return f"email:{email.lower().strip()}"
    if linkedin_url:
        # Normalize LinkedIn URL
        url = linkedin_url.lower().strip().rstrip("/")
        url = re.sub(r"https?://(www\.)?linkedin\.com/in/", "", url)
        return f"li:{url}"
    # Fallback: hash of normalized name + company
    name_key = _normalize_string(full_name)
    company_key = _normalize_string(company_name or "")
    combined = f"{name_key}|{company_key}"
    return f"name:{hashlib.md5(combined.encode()).hexdigest()[:16]}"


def generate_company_dedup_key(
    name: str,
    domain: Optional[str] = None,
    linkedin_url: Optional[str] = None,
) -> str:
    """
    Generate a deduplication key for a company.
    Priority: domain > linkedin > name hash
    """
    if domain:
        return f"domain:{domain.lower().strip().lstrip('www.').rstrip('/')}"
    if linkedin_url:
        url = linkedin_url.lower().strip().rstrip("/")
        url = re.sub(r"https?://(www\.)?linkedin\.com/company/", "", url)
        return f"li:{url}"
    name_key = _normalize_string(name)
    return f"name:{hashlib.md5(name_key.encode()).hexdigest()[:16]}"
