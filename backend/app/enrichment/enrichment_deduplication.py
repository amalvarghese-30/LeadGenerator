"""
Enrichment Deduplication: Combines, ranks, and deduplicates contact channels.
Prioritizes direct person contacts over generic company contacts.
"""
from typing import List, Dict, Any

STATUS_PRIORITY = {
    "human_reviewed": 5,
    "source_verified": 4,
    "format_checked": 3,
    "published": 2,
    "discovered": 1,
    "not_found": 0,
    "rejected": -1,
}

SCOPE_PRIORITY = {
    "person_direct_work": 5,
    "department": 4,
    "sales_enquiry": 3,
    "company_generic": 2,
    "company_switchboard": 2,
    "public_business_enquiry": 2,
    "media_enquiry": 2,
    "unclassified": 1,
}


class EnrichmentDeduplication:
    @staticmethod
    def deduplicate_channels(channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate channels by type and value, keeping highest quality entry."""
        by_key: Dict[str, Dict[str, Any]] = {}

        for ch in channels:
            ch_type = ch.get("type", "unknown")
            ch_val = str(ch.get("value", "")).lower().strip()
            if not ch_val:
                continue

            key = f"{ch_type}:{ch_val}"

            if key not in by_key:
                by_key[key] = dict(ch)
            else:
                existing = by_key[key]
                # Compare verification status
                new_status = ch.get("verification_status", "discovered")
                old_status = existing.get("verification_status", "discovered")
                if STATUS_PRIORITY.get(new_status, 1) > STATUS_PRIORITY.get(old_status, 1):
                    existing["verification_status"] = new_status
                    existing["confidence"] = max(existing.get("confidence", 0.5), ch.get("confidence", 0.5))

                # Upgrade scope if new is more direct
                new_scope = ch.get("scope", "unclassified")
                old_scope = existing.get("scope", "unclassified")
                if SCOPE_PRIORITY.get(new_scope, 1) > SCOPE_PRIORITY.get(old_scope, 1):
                    existing["scope"] = new_scope

                # Append or keep best evidence quote
                if not existing.get("evidence_quote") and ch.get("evidence_quote"):
                    existing["evidence_quote"] = ch["evidence_quote"]

                # Retain primary source URL
                if not existing.get("source_url") and ch.get("source_url"):
                    existing["source_url"] = ch["source_url"]

        # Sort channels: direct emails first, direct phones second, then company generic
        def _sort_key(c: Dict[str, Any]):
            scope_score = SCOPE_PRIORITY.get(c.get("scope", "unclassified"), 1)
            status_score = STATUS_PRIORITY.get(c.get("verification_status", "discovered"), 1)
            type_score = 3 if c.get("type") == "email" else (2 if c.get("type") == "phone" else 1)
            return (scope_score, type_score, status_score)

        sorted_channels = sorted(by_key.values(), key=_sort_key, reverse=True)
        return sorted_channels
