"""
Validate and sanitize AI model output before database persistence.

Guarantees:
- Generated emails and phone numbers are never persisted.
- Only explicitly supported extraction fields are accepted.
- Null-like strings are normalized to None.
- verification_status is always pending.
- Relationship types are validated.
- Low-confidence entities are flagged for review.
- Malformed entities are rejected safely.
"""
import json
import logging
import math
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

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

_FORBIDDEN_FIELDS = {
    "email", "phone", "mobile", "telephone", "fax"
}

_ALLOWED_FIELDS = {
    "person_name",
    "designation",
    "company_name",
    "industry",
    "relationship_type",
    "service_category",
    "evidence_quote",
    "source_url",
    "confidence",
    "verification_status",
}

_NULL_VALUES = {"", "null", "none", "n/a", "na", "not available"}
_MIN_CONFIDENCE = 0.4
_MAX_EVIDENCE_CHARS = 500


def _normalize_text(value):
    if value is None:
        return None

    if not isinstance(value, str):
        return None

    value = value.strip()

    if value.lower() in _NULL_VALUES:
        return None

    return value or None


class OutputValidator:
    """Validates and sanitizes raw AI extraction output."""

    def validate_extraction_output(
        self, raw_output: str, source_url: str
    ) -> Optional[List[Dict]]:

        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("AI output JSON parse error: %s", exc)
            return None

        if not isinstance(data, dict):
            logger.warning("AI output is not a JSON object")
            return None

        entities_raw = data.get("entities")

        if not isinstance(entities_raw, list):
            logger.warning("'entities' field is not a list")
            return None

        validated = []

        for idx, entity in enumerate(entities_raw):
            if not isinstance(entity, dict):
                logger.debug("Skipping invalid entity at index %d", idx)
                continue

            result = self._validate_entity(entity, source_url)

            if result is not None:
                validated.append(result)

        return validated or None

    def _validate_entity(
        self, entity: Dict, source_url: str
    ) -> Optional[Dict]:

        # Reject malformed keys rather than guessing their meaning.
        clean = {
            key: value
            for key, value in entity.items()
            if key in _ALLOWED_FIELDS
        }

        # Never trust model-generated contact details.
        for field in _FORBIDDEN_FIELDS:
            if field in entity:
                logger.info("Stripping forbidden AI field: %s", field)

        # Normalize all supported text fields.
        text_fields = (
            "person_name",
            "designation",
            "company_name",
            "industry",
            "service_category",
            "evidence_quote",
        )

        for field in text_fields:
            clean[field] = _normalize_text(clean.get(field))

        # At least one real identity must be present.
        if not clean.get("person_name") and not clean.get("company_name"):
            logger.debug("Discarding entity without a valid identity")
            return None

        # Validate relationship classification.
        relationship = clean.get("relationship_type")

        if (
            not isinstance(relationship, str)
            or relationship not in VALID_RELATIONSHIP_TYPES
        ):
            clean["relationship_type"] = "unclear_relationship"

        # Parse and constrain confidence.
        try:
            confidence = float(clean.get("confidence", 0.0))
            if not math.isfinite(confidence):
                confidence = 0.0
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))
        clean["confidence"] = confidence

        if confidence < _MIN_CONFIDENCE:
            clean["needs_review"] = True

        # Always use the authoritative URL supplied by the caller.
        clean["source_url"] = source_url

        if clean.get("evidence_quote"):
            clean["evidence_quote"] = clean["evidence_quote"][
                :_MAX_EVIDENCE_CHARS
            ]

        # Model output can never mark a record as verified.
        clean["verification_status"] = "pending"

        return clean
