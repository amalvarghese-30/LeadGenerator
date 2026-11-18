"""
Client identification and classification pipeline.

Order of operations per page:
  1. Multi-signal page classification (TextExtractor)
  2. Multi-signal deterministic extraction via PageAnalyzer (each candidate classified independently)
  3. Optional NVIDIA augmentation (merges with deterministic results without overwriting evidence)
  4. Strict validation (EvidenceValidator + NameValidator + Competitor Blacklist)
  5. Distinction between:
     - Confirmed client references (case studies, testimonials, portfolio, client profiles)
     - Company-only references
     - Non-client mentions (featured personalities, collaborators, ordinary mentions)
     - Rejected false positives with explicit rejection reasons

Every persisted record has verification_status = "pending". AI cannot self-verify.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple, Optional

from app.ai.nvidia_client import NvidiaClient
from app.extraction.evidence_validator import EvidenceValidator, CLIENT_CUSTOMER_RELATIONSHIPS
from app.extraction.page_analyzer import PageAnalyzer
from app.extraction.text_extraction import TextExtractor

logger = logging.getLogger(__name__)


class ClientClassifier:
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.page_analyzer = PageAnalyzer()
        self.evidence_validator = EvidenceValidator()
        self.nvidia_client = NvidiaClient()

    async def process_page(
        self,
        page_data: Dict[str, Any],
        provider_id: str,
        competitor_domain: Optional[str] = None,
        competitor_brand: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Backwards-compatible interface: returns list of validated client references.
        """
        results, _, _ = await self.process_page_detailed(
            page_data, provider_id, competitor_domain=competitor_domain, competitor_brand=competitor_brand
        )
        return results

    async def process_page_detailed(
        self,
        page_data: Dict[str, Any],
        provider_id: str,
        competitor_domain: Optional[str] = None,
        competitor_brand: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process a page and return:
        (valid_references, rejected_candidates, page_metadata)
        """
        url = page_data.get("url", "")
        title = page_data.get("page_title") or page_data.get("title", "")
        text = page_data.get("main_text", "")
        h1 = page_data.get("h1", "")
        h2s = page_data.get("h2s", [])

        if not text or len(text.strip()) < 80:
            logger.debug("Skipping page with insufficient text: %s", url)
            return [], [], {"skipped": True, "reason": "Insufficient content (< 80 chars)"}

        # 1. Multi-signal page classification
        page_meta = self.text_extractor.classify_page_relevance(
            url=url,
            title=title,
            text=text,
            h1=h1,
            h2s=h2s,
        )

        if not page_meta["is_client_reference_page"]:
            logger.debug(
                "Page not a client reference page (category=%s, score=%d): %s",
                page_meta.get("page_category"),
                page_meta.get("relevance_score", 0),
                url,
            )
            return [], [], page_meta

        # 2. Deterministic rich extraction
        deterministic = self.page_analyzer.analyze(text, url, title)

        # 3. NVIDIA augmentation if available
        ai_results: List[Dict[str, Any]] = []
        if await self.nvidia_client.is_available():
            try:
                raw = await self.nvidia_client.extract_entities(text, url, title)
                if raw:
                    ai_results = raw
            except Exception as e:
                logger.warning("NVIDIA entity extraction error: %s", e)

        # 4. Merge results without overwriting deterministic high-precision evidence
        merged = self._merge(deterministic, ai_results, url)

        # 5. Strict multi-stage validation with competitor blacklist
        valid_references: List[Dict[str, Any]] = []
        rejected_candidates: List[Dict[str, Any]] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for ref in merged:
            ref["provider_id"] = provider_id
            ref["page_category"] = page_meta["page_category"]
            ref["collected_at"] = now_iso
            ref["verification_status"] = "pending"

            # If page is a Published Client Profile, classify featured client as published_customer_profile
            if page_meta.get("page_category") == "Published Client Profile" and ref.get("relationship_type") in (
                "ordinary_mention", "featured_personality", "unclear_relationship"
            ):
                ref["relationship_type"] = "published_customer_profile"

            # Check evidence validity with competitor blacklist
            is_valid, rejection_reasons = self.evidence_validator.validate(
                ref,
                source_text=text,
                competitor_domain=competitor_domain,
                competitor_brand=competitor_brand,
            )

            # Check if this relationship represents a real customer relationship
            rel = ref.get("relationship_type", "unclear_relationship")
            if rel not in CLIENT_CUSTOMER_RELATIONSHIPS:
                rejection_reasons.append(f"Relationship type '{rel}' is not a client/customer relationship")
                is_valid = False

            if is_valid:
                valid_references.append(ref)
            else:
                rejected_record = {
                    **ref,
                    "rejection_reasons": rejection_reasons,
                    "rejected_at": now_iso,
                }
                rejected_candidates.append(rejected_record)
                logger.debug(
                    "Rejected candidate: %s | reasons: %s",
                    ref.get("person_name") or ref.get("company_name"),
                    rejection_reasons,
                )

        logger.info(
            "Extracted from %s: %d valid client references, %d rejected candidates (det=%d, ai=%d)",
            url, len(valid_references), len(rejected_candidates), len(deterministic), len(ai_results),
        )
        return valid_references, rejected_candidates, page_meta

    def _merge(self, det: Optional[List[Dict]], ai: Optional[List[Dict]], url: str) -> List[Dict]:
        """Merge deterministic and AI results, prioritizing deterministic evidence."""
        by_key: Dict[str, Dict] = {}

        for ref in (det or []):
            key = (ref.get("person_name") or f"comp:{ref.get('company_name')}" or "").lower()
            if not key:
                continue
            by_key[key] = dict(ref)

        for ref in (ai or []):
            person = ref.get("person_name")
            comp = ref.get("company_name")
            key = (person or f"comp:{comp}" or "").lower()
            if not key:
                continue

            if key in by_key:
                # Fill missing fields only
                existing = by_key[key]
                for field in ("designation", "company_name", "industry", "service_category"):
                    if not existing.get(field) and ref.get(field):
                        existing[field] = ref[field]
                existing["confidence"] = max(
                    float(existing.get("confidence", 0.7)),
                    float(ref.get("confidence", 0.5)),
                )
                existing["extraction_method"] = "deterministic+ai"
            else:
                by_key[key] = {
                    "person_name": ref.get("person_name"),
                    "designation": ref.get("designation"),
                    "company_name": ref.get("company_name"),
                    "industry": ref.get("industry"),
                    "relationship_type": ref.get("relationship_type", "unclear_relationship"),
                    "service_category": ref.get("service_category"),
                    "source_url": url,
                    "evidence_quote": ref.get("evidence_quote") or f"Mentioned on {url}",
                    "confidence": float(ref.get("confidence", 0.5)),
                    "extraction_method": "nvidia_nemotron",
                }

        out = []
        for ref in by_key.values():
            ref.setdefault("source_url", url)
            out.append(ref)
        return out
