"""
Evidence Validator.
Validates extraction results prior to persistence.
Guarantees source attribution, evidence quotation correspondence,
validates person and company entities, validates relationship context,
enforces competitor identity blacklisting (never save competitor as client),
and enforces pending verification status (AI cannot self-verify).
"""
import hashlib
import re
from typing import Dict, Tuple, List, Any, Optional
from urllib.parse import urlparse

from app.extraction.name_validator import NameValidator

# Supported explicit relationship classifications
VALID_RELATIONSHIP_TYPES = {
    "confirmed_client",
    "confirmed_client_case_study",
    "case_study_client",
    "client_testimonial",
    "testimonial_client",
    "client_portfolio_reference",
    "published_customer_profile",
    "featured_personality",
    "collaborator",
    "partner",
    "supplier",
    "sponsor",
    "affiliate",
    "ordinary_mention",
    "unclear_relationship",
}

# Client relationship types that represent actual customer relationships
CLIENT_CUSTOMER_RELATIONSHIPS = {
    "confirmed_client",
    "confirmed_client_case_study",
    "case_study_client",
    "client_testimonial",
    "testimonial_client",
    "client_portfolio_reference",
    "published_customer_profile",
}

GENERIC_UI_PHRASES = {
    "view more", "learn more", "our services", "contact us", "read more",
    "case studies", "case study", "view project", "our clients", "portfolio",
    "terms of service", "privacy policy", "all rights reserved", "cookie policy",
    "about us", "home", "services", "navigation", "menu", "get started",
    "request a quote", "click here", "read story", "explore more", "see all",
    "client stories", "testimonials", "what we do", "who we are", "back to top"
}


class EvidenceValidator:
    """Strict validator for extracted client references and evidence quotes."""

    def __init__(self):
        self.name_validator = NameValidator()

    def validate(
        self,
        extraction_result: Dict[str, Any],
        source_text: Optional[str] = None,
        competitor_domain: Optional[str] = None,
        competitor_brand: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Validate extracted reference against evidence requirements.
        Returns: (is_valid, list_of_rejection_reasons)
        """
        rejection_reasons: List[str] = []

        # 1. Source URL must be present and valid
        source_url = extraction_result.get("source_url") or extraction_result.get("original_provider_url")
        if not source_url:
            rejection_reasons.append("Missing source_url")
        else:
            try:
                parsed = urlparse(source_url)
                if not parsed.scheme or not parsed.netloc:
                    rejection_reasons.append("Malformed source URL")
            except Exception:
                rejection_reasons.append("Invalid source URL")

        # 2. Must identify at least a valid person name or company name
        person_name = extraction_result.get("person_name")
        company_name = extraction_result.get("company_name")
        quote = extraction_result.get("evidence_quote") or ""

        if not person_name and not company_name:
            rejection_reasons.append("No person name or company name provided")

        # 3. If person name is provided, must pass strict NameValidator
        if person_name:
            is_valid_name, name_issues = self.name_validator.validate_person_name(
                person_name, context=quote
            )
            if not is_valid_name:
                rejection_reasons.extend(name_issues)

        # 4. If company name is provided, validate it's not a person, navigation phrase, or competitor itself
        if company_name:
            comp_clean = str(company_name).strip()
            if len(comp_clean) < 2 or len(comp_clean) > 80:
                rejection_reasons.append(f"Invalid company name length: '{comp_clean}'")

            comp_lower = comp_clean.lower()
            if comp_lower in GENERIC_UI_PHRASES:
                rejection_reasons.append(f"Company name is generic navigation/UI phrase: '{comp_clean}'")

            # Competitor self-reference blacklist
            if competitor_brand and (
                comp_lower == competitor_brand.lower()
                or comp_lower in competitor_brand.lower()
                or competitor_brand.lower() in comp_lower
            ):
                rejection_reasons.append(f"Entity matches target competitor brand '{competitor_brand}'")

            if competitor_domain:
                clean_cd = competitor_domain.lower().replace("www.", "")
                root_cd = clean_cd.split(".")[0]
                if len(root_cd) >= 4 and root_cd in comp_lower:
                    rejection_reasons.append(f"Entity matches competitor domain name '{competitor_domain}'")

        # 5. Evidence quotation correspondence
        ext_method = extraction_result.get("extraction_method")
        min_quote_len = 5 if ext_method in ("portfolio_dom", "portfolio_logo_dom") else 15
        if not quote:
            rejection_reasons.append("Missing evidence quotation")
        elif len(quote) < min_quote_len:
            rejection_reasons.append(f"Evidence quotation is too short (< {min_quote_len} characters)")
        else:
            quote_lower = quote.lower()
            text_lower = (source_text or "").lower()

            if person_name:
                p_lower = person_name.lower()
                name_in_quote = p_lower in quote_lower
                name_in_text = p_lower in text_lower if source_text else True
                if not (name_in_quote or name_in_text):
                    rejection_reasons.append(f"Person name '{person_name}' is not found in evidence quote or source text")

            if company_name:
                c_lower = company_name.lower()
                comp_in_quote = c_lower in quote_lower
                comp_in_text = c_lower in text_lower if source_text else True
                if not (comp_in_quote or comp_in_text):
                    rejection_reasons.append(f"Company name '{company_name}' is not found in evidence quote or source text")

        # 6. Relationship type check
        rel_type = extraction_result.get("relationship_type", "unclear_relationship")
        if rel_type not in VALID_RELATIONSHIP_TYPES:
            rejection_reasons.append(f"Unsupported relationship type: '{rel_type}'")

        # 7. Check that client relationship claim is actually supported by evidence
        if rel_type in CLIENT_CUSTOMER_RELATIONSHIPS and quote:
            quote_lower = quote.lower()
            has_client_keyword = any(k in quote_lower for k in [
                "testimonial", "case study", "client", "customer", "project for",
                "worked with", "helped", "portfolio", "success", "results",
                "says", "review", "feedback", "rating", "brand", "partner", "delivered"
            ])
            has_role = bool(extraction_result.get("designation") or extraction_result.get("company_name"))
            if not has_client_keyword and not has_role:
                rejection_reasons.append("No contextual evidence supporting client/customer relationship")

        # 8. Minimum Confidence Check (if confidence explicitly provided, must be >= 0.60)
        if "confidence" in extraction_result and float(extraction_result["confidence"]) < 0.60:
            rejection_reasons.append(f"Confidence score {float(extraction_result['confidence']):.2f} is below minimum threshold 0.60")

        # 9. Prevent hallucinated emails
        if "email" in extraction_result and extraction_result["email"]:
            if extraction_result.get("extraction_method") == "nvidia_nemotron":
                extraction_result.pop("email", None)

        # 10. Enforce mandatory verification status
        extraction_result["verification_status"] = "pending"

        # 11. Generate deterministic source hash
        extraction_result["source_hash"] = self.hash_evidence(
            source_url or "",
            quote or ""
        )

        is_valid = len(rejection_reasons) == 0
        return is_valid, rejection_reasons

    def hash_evidence(self, source_url: str, quote: str) -> str:
        content = f"{source_url}|{quote or ''}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
