"""
Validate and sanitize AI model output before database persistence.

Key guarantees enforced here:
- Generated emails are always stripped (never persisted).
- verification_status is always forced to "pending".
- Relationship types are validated against the allowed set.
- Low-confidence entities are flagged for review (not silently dropped).
- Malformed JSON returns None rather than raising.
"""
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_RELATIONSHIP_TYPES: set = {
    "confirmed_client_case_study",
    "client_testimonial",
    "client_portfolio_reference",
    "published_customer_profile",
    "featured_personality",
    "collaborator",
    "ordinary_mention",
    "unclear_relationship",
}

# Fields that must never be stored from AI output
_FORBIDDEN_FIELDS = {"email", "phone", "mobile", "telephone", "fax"}

_MIN_CONFIDENCE = 0.4
_MAX_EVIDENCE_CHARS = 500


class OutputValidator:
    """Validates and sanitises raw AI output into safe, structured dicts."""

    def validate_extraction_output(
        self, raw_output: str, source_url: str
    ) -> Optional[List[Dict]]:
        """
        Parse and validate AI output.

        Rules applied to every entity:
        - Strip generated emails / phones (never allowed from AI)
        - Force verification_status = "pending"
        - Validate relationship_type against the allowed enum
        - Flag low-confidence entities (confidence < 0.4) with needs_review=True
        - Reject entities that have neither person_name nor company_name
        - Truncate evidence_quote to 500 chars
        - Inject source_url from the caller (not from AI output)

        Returns:
            List of validated entity dicts, or None if output is unparseable
            or no valid entities remain.
        """
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("AI output JSON parse error: %s", exc)
            return None

        if not isinstance(data, dict):
            logger.warning("AI output is not a JSON object: %r", type(data))
            return None

        entities_raw = data.get("entities", [])
        if not isinstance(entities_raw, list):
            logger.warning("'entities' field is not a list")
            return None

        validated: List[Dict] = []
        for idx, entity in enumerate(entities_raw):
            if not isinstance(entity, dict):
                logger.debug("Skipping non-dict entity at index %d", idx)
                continue

            result = self._validate_entity(entity, source_url)
            if result is not None:
                validated.append(result)

        return validated if validated else None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_entity(self, entity: Dict, source_url: str) -> Optional[Dict]:
        """
        Validate a single entity dict.  Returns cleaned dict or None if the
        entity must be discarded entirely.
        """
        # Must identify at least one party
        if not entity.get("person_name") and not entity.get("company_name"):
            logger.debug("Discarding entity with no name or company: %r", entity)
            return None

        # Work on a copy so we don't mutate the caller's data
        clean: Dict = dict(entity)

        # --- Security: strip forbidden contact fields ---
        for field in _FORBIDDEN_FIELDS:
            if field in clean:
                logger.info(
                    "Stripping forbidden field '%s' from AI output (source: %s)",
                    field,
                    source_url,
                )
                clean.pop(field)

        # --- Always force pending ---
        clean["verification_status"] = "pending"

        # --- Validate relationship_type ---
        rel = clean.get("relationship_type", "")
        if rel not in VALID_RELATIONSHIP_TYPES:
            logger.debug(
                "Unknown relationship_type %r → unclear_relationship", rel
            )
            clean["relationship_type"] = "unclear_relationship"

        # --- Confidence handling ---
        try:
            confidence = float(clean.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        clean["confidence"] = confidence

        if confidence < _MIN_CONFIDENCE:
            clean["needs_review"] = True
            logger.debug(
                "Low-confidence entity (%.2f) flagged needs_review: %s",
                confidence,
                clean.get("person_name") or clean.get("company_name"),
            )

        # --- Always inject authoritative source_url ---
        clean["source_url"] = source_url

        # --- Truncate evidence quote ---
        if clean.get("evidence_quote"):
            clean["evidence_quote"] = str(clean["evidence_quote"])[:_MAX_EVIDENCE_CHARS]

        # --- Sanitize text fields (nullify empty strings) ---
        for field in ("person_name", "designation", "company_name", "industry",
                      "service_category"):
            if clean.get(field) == "":
                clean[field] = None

        return clean
