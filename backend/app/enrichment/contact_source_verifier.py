"""
Contact Source Verifier: Evaluates source provenance, evidence presence,
domain match, and validation checks to assign an accurate verification status
to each contact channel.
"""
from typing import Dict, Any, Optional

STATUS_HIERARCHY = [
    "not_found",
    "discovered",
    "published",
    "format_checked",
    "source_verified",
    "human_reviewed",
]


class ContactSourceVerifier:
    @staticmethod
    def determine_channel_status(
        ch_type: str,
        value: str,
        validation_info: Dict[str, Any],
        source_url: Optional[str] = None,
        is_official_domain: bool = False,
        has_evidence_quote: bool = False,
        human_reviewed: bool = False,
        is_rejected: bool = False,
    ) -> str:
        """
        Determines multi-signal verification status:
        - rejected: if marked rejected or fundamentally invalid syntax
        - human_reviewed: if verified by a human user
        - source_verified: format checked + confirmed on official company/personal domain + evidence quote
        - format_checked: syntax + MX (for email) or is_valid (for phone) passed
        - published: extracted from visible webpage with evidence quote
        - discovered: regex matched only
        """
        if is_rejected:
            return "rejected"

        if human_reviewed:
            return "human_reviewed"

        if not validation_info.get("syntax_valid", False):
            return "rejected"

        if ch_type == "email":
            mx_ok = validation_info.get("mx_record_found", False)
            company_match = validation_info.get("company_attributed", False) or is_official_domain

            if mx_ok and company_match and has_evidence_quote:
                return "source_verified"
            if mx_ok:
                return "format_checked"
            if has_evidence_quote:
                return "published"
            return "discovered"

        elif ch_type == "phone":
            is_valid = validation_info.get("is_valid", False)
            if is_valid and is_official_domain and has_evidence_quote:
                return "source_verified"
            if is_valid:
                return "format_checked"
            if has_evidence_quote:
                return "published"
            return "discovered"

        elif ch_type in ("contact_form", "social", "website"):
            if is_official_domain:
                return "source_verified"
            if has_evidence_quote:
                return "published"
            return "discovered"

        return "discovered"
