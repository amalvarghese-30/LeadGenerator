"""
Deduplication key generation and entity normalization utilities.
Provides deterministic, collision-resistant deduplication keys for:
- Contacts (by verified email, canonical LinkedIn profile, or normalized name + company)
- Companies (by canonical domain, canonical LinkedIn company, or normalized corporate name)
- Leads (by contact + company combination, handling null company IDs safely)
"""
import hashlib
import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse

# Corporate legal designators to strip for company normalization
LEGAL_ENTITIES = [
    r'\binc\.?\b', r'\bllc\.?\b', r'\bl\.l\.c\.?\b', r'\bltd\.?\b', r'\bcorp\.?\b',
    r'\bcorporation\b', r'\bcompany\b', r'\bco\.?\b', r'\blimited\b', r'\bgmbh\b',
    r'\bpty\.?\b', r'\bpvt\.?\b', r'\bllp\.?\b', r'\bl\.p\.?\b', r'\bpllc\.?\b',
]
LEGAL_ENTITIES_REGEX = re.compile('|'.join(LEGAL_ENTITIES), re.IGNORECASE)


def normalize_string(s: Optional[str]) -> str:
    """Lowercase, strip accents, remove punctuation and extra whitespace."""
    if not s:
        return ""
    # Unicode normalize
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Remove non-alphanumeric except spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_company_name(name: Optional[str]) -> str:
    """Normalize business name by removing corporate entity designators and punctuation."""
    if not name:
        return ""
    norm = normalize_string(name)
    # Strip legal entity suffixes
    norm = LEGAL_ENTITIES_REGEX.sub("", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def normalize_domain(domain_or_url: Optional[str]) -> Optional[str]:
    """Extract and normalize canonical domain from a URL or domain string."""
    if not domain_or_url:
        return None
    val = domain_or_url.strip().lower()
    if not val.startswith(("http://", "https://")):
        val = f"http://{val}"
    try:
        parsed = urlparse(val)
        domain = parsed.netloc or parsed.path
        # Remove port if present
        domain = domain.split(":")[0]
        # Remove leading www.
        if domain.startswith("www."):
            domain = domain[4:]
        domain = domain.strip().rstrip("/")
        return domain if len(domain) > 3 else None
    except Exception:
        return None


def normalize_linkedin_url(url: Optional[str], entity_type: str = "in") -> Optional[str]:
    """Normalize personal or company LinkedIn URL to canonical handle."""
    if not url:
        return None
    u = url.strip().lower().rstrip("/")
    pattern = rf"https?://(?:www\.)?linkedin\.com/{entity_type}/([^/?#]+)"
    match = re.search(pattern, u)
    if match:
        return match.group(1).strip()
    # Fallback if just handle was provided
    cleaned = re.sub(r"[^a-z0-9\-]", "", u)
    return cleaned if cleaned else None


def generate_contact_dedup_key(
    full_name: str,
    email: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    company_name: Optional[str] = None,
    company_id: Optional[str] = None,
) -> str:
    """
    Generate a deduplication key for a contact.
    Priority order:
      1. Explicit published business email
      2. Canonical personal LinkedIn profile
      3. Normalized full name + Company association (ID or normalized name)
      4. Fallback: Normalized full name (isolated individual)
    """
    if email and "@" in email:
        clean_email = email.lower().strip()
        return f"email:{clean_email}"

    if linkedin_url:
        li_handle = normalize_linkedin_url(linkedin_url, entity_type="in")
        if li_handle:
            return f"li:{li_handle}"

    name_key = normalize_string(full_name)
    comp_ref = company_id or normalize_company_name(company_name or "")

    if comp_ref:
        combined = f"{name_key}|{comp_ref}"
        return f"name_comp:{hashlib.sha256(combined.encode()).hexdigest()[:20]}"

    return f"name:{hashlib.sha256(name_key.encode()).hexdigest()[:20]}"


def generate_company_dedup_key(
    name: str,
    domain: Optional[str] = None,
    website: Optional[str] = None,
    linkedin_url: Optional[str] = None,
) -> str:
    """
    Generate a deduplication key for a company.
    Priority order:
      1. Canonical domain / website
      2. Canonical company LinkedIn profile
      3. Normalized corporate business name
    """
    canon_domain = normalize_domain(domain or website)
    if canon_domain:
        return f"domain:{canon_domain}"

    if linkedin_url:
        li_handle = normalize_linkedin_url(linkedin_url, entity_type="company")
        if li_handle:
            return f"li:{li_handle}"

    norm_name = normalize_company_name(name)
    return f"name:{hashlib.sha256(norm_name.encode()).hexdigest()[:20]}"


def generate_lead_dedup_key(contact_id: str, company_id: Optional[str] = None) -> str:
    """Generate idempotent lead deduplication key handling null company IDs safely."""
    cid = str(contact_id).strip()
    comp = str(company_id).strip() if company_id else "none"
    return f"lead:{cid}|{comp}"
