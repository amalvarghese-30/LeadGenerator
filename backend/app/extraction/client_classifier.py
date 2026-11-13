"""
Client identification pipeline.

Order of operations per page:
  1. Rule-based page classification (TextExtractor)
  2. Deterministic rich extraction via PageAnalyzer (always runs)
  3. Optional NVIDIA augmentation (merges with deterministic results)

Every returned record has verification_status = "pending". AI cannot self-verify.
"""
import logging
from datetime import datetime
from typing import Dict, List

from app.ai.nvidia_client import NvidiaClient
from app.extraction.evidence_validator import EvidenceValidator
from app.extraction.page_analyzer import PageAnalyzer
from app.extraction.text_extraction import TextExtractor

logger = logging.getLogger(__name__)


class ClientClassifier:
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.page_analyzer = PageAnalyzer()
        self.evidence_validator = EvidenceValidator()
        self.nvidia_client = NvidiaClient()

    async def process_page(self, page_data: Dict, provider_id: str) -> List[Dict]:
        url = page_data.get("url", "")
        title = page_data.get("title", "")
        text = page_data.get("main_text", "")

        if not text or len(text) < 100:
            logger.debug("Skipping page with insufficient text: %s", url)
            return []

        page_meta = self.text_extractor.classify_page_relevance(url, title, text)
        if not page_meta["is_client_reference_page"]:
            logger.debug(
                "Page not a client reference page (score=%d): %s",
                page_meta.get("relevance_score", 0),
                url,
            )
            return []

        # Deterministic extraction — always runs
        deterministic = self.page_analyzer.analyze(text, url, title)

        # NVIDIA augmentation if available
        ai_results: List[Dict] = []
        ai_used = False
        if await self.nvidia_client.is_available():
            raw = await self.nvidia_client.extract_entities(text, url, title)
            if raw:
                ai_results = raw
                ai_used = True

        merged = self._merge(deterministic, ai_results, url, page_meta)

        # Final validation & filter
        final: List[Dict] = []
        for ref in merged:
            ref["provider_id"] = provider_id
            ref["page_category"] = page_meta["page_category"]
            ref["collected_at"] = datetime.utcnow().isoformat()
            ref["verification_status"] = "pending"

            is_valid, issues = self.evidence_validator.validate(ref)
            if is_valid:
                final.append(ref)
            else:
                logger.debug("Reference failed validation (%s): %s",
                             ref.get("person_name") or ref.get("company_name"), issues)

        logger.info(
            "Extracted %d client references from %s (deterministic=%d, ai=%d)",
            len(final), url, len(deterministic), len(ai_results),
        )
        return final

    # ------------------------------------------------------------------
    def _merge(self, det: List[Dict], ai: List[Dict], url: str, page_meta: Dict) -> List[Dict]:
        """Merge deterministic and AI results, preferring more complete fields."""
        by_name: Dict[str, Dict] = {}

        for ref in det:
            key = (ref.get("person_name") or "").lower()
            if not key:
                continue
            by_name[key] = dict(ref)

        for ref in ai:
            key = (ref.get("person_name") or ref.get("company_name") or "").lower()
            if not key:
                continue
            if key in by_name:
                # Merge — AI fills in missing fields only
                existing = by_name[key]
                for field in ("designation", "company_name", "industry", "service_category",
                              "relationship_type", "evidence_quote"):
                    if not existing.get(field) and ref.get(field):
                        existing[field] = ref[field]
                # Promote confidence if AI agrees with deterministic finding
                existing["confidence"] = max(
                    float(existing.get("confidence", 0.5)),
                    float(ref.get("confidence", 0.5)),
                )
                existing["extraction_method"] = "deterministic+ai"
            else:
                by_name[key] = {
                    "person_name": ref.get("person_name"),
                    "designation": ref.get("designation"),
                    "company_name": ref.get("company_name"),
                    "industry": ref.get("industry"),
                    "relationship_type": ref.get("relationship_type", "unclear_relationship"),
                    "service_category": ref.get("service_category"),
                    "source_url": url,
                    "evidence_quote": ref.get("evidence_quote"),
                    "confidence": float(ref.get("confidence", 0.5)),
                    "extraction_method": "nvidia_nemotron",
                }

        # Ensure every result has required fields
        out = []
        for ref in by_name.values():
            ref.setdefault("source_url", url)
            out.append(ref)
        return out