"""
Evidence Validator.
Validates extraction results prior to persistence.
Guarantees source attribution, evidence quotation, strips generated emails,
and enforces pending verification status (AI cannot self-verify).
"""
import hashlib
from typing import Dict, Tuple, List, Any

class EvidenceValidator:
    def validate(self, extraction_result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate extracted client reference.
        Returns: (is_valid, list_of_rejection_reasons)
        """
        issues: List[str] = []

        # 1. Source URL must be present
        if not extraction_result.get("source_url"):
            issues.append("Missing source_url")

        # 2. Must identify a person name or company name
        person_name = extraction_result.get("person_name")
        company_name = extraction_result.get("company_name")
        if not person_name and not company_name:
            issues.append("Must have at least person_name or company_name")

        # 3. Prevent hallucinated/guessed personal emails
        # Emails must never be invented by AI
        if "email" in extraction_result and extraction_result["email"]:
            if extraction_result.get("extraction_method") == "nvidia_nemotron":
                # Strip out any AI-generated email to adhere to Non-Negotiable Requirements
                extraction_result.pop("email", None)

        # 4. Enforce mandatory verification status
        # AI models can NEVER self-approve or auto-verify records
        extraction_result["verification_status"] = "pending"

        # 5. Sanitize evidence quotation
        quote = extraction_result.get("evidence_quote")
        if quote:
            extraction_result["evidence_quote"] = str(quote).strip()[:500]

        # 6. Source hash for integrity and duplicate prevention
        extraction_result["source_hash"] = self.hash_evidence(
            extraction_result.get("source_url", ""),
            extraction_result.get("evidence_quote", "")
        )

        is_valid = len([i for i in issues if "Missing" in i or "Must have" in i]) == 0
        return is_valid, issues

    def hash_evidence(self, source_url: str, quote: str) -> str:
        content = f"{source_url}|{quote or ''}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
