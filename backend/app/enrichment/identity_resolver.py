"""
Identity Resolver: Constructs an authoritative identity profile for a Contact
prior to launching external search or crawling.
Combines Person + Company attributes to generate high-precision, low-false-positive
query targets and validation anchors.
"""
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from pydantic import BaseModel, Field


class IdentityProfile(BaseModel):
    contact_id: str
    full_name: str
    first_name: str
    last_name: str
    alternative_spellings: List[str] = Field(default_factory=list)
    designation: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_website: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_handle: Optional[str] = None
    personal_website: Optional[str] = None
    verified_urls: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)


class IdentityResolver:
    @staticmethod
    def resolve(contact: Dict[str, Any], company: Optional[Dict[str, Any]] = None) -> IdentityProfile:
        full_name = (contact.get("full_name") or "").strip()
        # Remove leading honorifics like Dr., Mr., Adv., CA, Prof., etc. from the full name
        cleaned_name = re.sub(r'^(?:dr|mr|mrs|ms|adv|ca|prof|hon)\.?\s+', '', full_name, flags=re.IGNORECASE).strip()
        parts = cleaned_name.split() if cleaned_name else full_name.split()
        first_name = parts[0] if parts else ""
        last_name = parts[-1] if len(parts) > 1 else ""

        # Generate alternative name variations
        alt_spellings = []
        if len(parts) >= 3:
            alt_spellings.append(f"{parts[0]} {parts[-1]}")
            alt_spellings.append(f"{parts[0]} {parts[1][0]}. {parts[-1]}")
        elif len(parts) == 2:
            alt_spellings.append(f"{parts[0][0]}. {parts[1]}")

        company_name = contact.get("company_name") or (company.get("name") if company else None)
        company_domain = company.get("domain") if company else None
        company_website = company.get("website") if company else None

        # LinkedIn & Socials
        prof_urls = contact.get("professional_urls", {})
        linkedin = prof_urls.get("linkedin") or contact.get("linkedin_url")
        linkedin_handle = None
        if linkedin:
            m = re.search(r'linkedin\.com/(?:in|company)/([a-zA-Z0-9_\-]+)', linkedin)
            if m:
                linkedin_handle = m.group(1)

        # Check for personal website in professional URLs
        personal_site = prof_urls.get("website") or prof_urls.get("personal_website")

        # Compile verified URLs
        verified_urls = []
        if linkedin:
            verified_urls.append(linkedin)
        if company_website:
            verified_urls.append(company_website)
        for k, v in prof_urls.items():
            if v and v.startswith("http") and v not in verified_urls:
                verified_urls.append(v)

        # Build precision search queries (Always pair Name with Company or Role)
        queries = []
        if company_name and full_name:
            queries.append(f'"{full_name}" "{company_name}" contact')
            queries.append(f'"{full_name}" "{company_name}" email')
            queries.append(f'"{full_name}" "{company_name}" phone')
            queries.append(f'"{full_name}" "{company_name}"')
        
        if full_name:
            queries.append(f'"{full_name}" official website')
            queries.append(f'"{full_name}" professional website')
            if contact.get("designation"):
                queries.append(f'"{full_name}" "{contact.get("designation")}" contact')

        if company_name and not company_domain:
            queries.append(f'"{company_name}" official website contact')

        return IdentityProfile(
            contact_id=str(contact.get("id") or contact.get("_id") or ""),
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            alternative_spellings=alt_spellings,
            designation=contact.get("designation"),
            company_name=company_name,
            company_domain=company_domain,
            company_website=company_website,
            linkedin_url=linkedin,
            linkedin_handle=linkedin_handle,
            personal_website=personal_site,
            verified_urls=verified_urls,
            search_queries=queries,
        )
