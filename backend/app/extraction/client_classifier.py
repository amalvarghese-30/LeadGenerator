"""
Client identification and classification pipeline.

Order of operations per page:
  1. Multi-signal page classification (TextExtractor with URL, headings, DOM grids)
  2. Dedicated Portfolio DOM Extraction (PortfolioExtractor - cards, grids, outbound links)
  3. Multi-signal deterministic extraction via PageAnalyzer (each candidate classified independently)
  4. Optional NVIDIA augmentation (merges with deterministic results without overwriting evidence)
  5. Strict validation (EvidenceValidator + NameValidator + Competitor Blacklist)
  6. Distinction between:
     - Confirmed client references (case studies, testimonials, portfolio, client profiles)
     - Company-only references
     - Non-client mentions (featured personalities, collaborators, ordinary mentions)
     - Rejected false positives with explicit rejection reasons

Every persisted record has verification_status = "pending_review". AI cannot self-verify.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple, Optional

from app.ai.nvidia_client import NvidiaClient
from app.extraction.evidence_validator import EvidenceValidator, CLIENT_CUSTOMER_RELATIONSHIPS
from app.extraction.page_analyzer import PageAnalyzer
from app.extraction.portfolio_extractor import PortfolioExtractor
from app.extraction.text_extraction import TextExtractor

logger = logging.getLogger(__name__)


class ClientClassifier:
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.portfolio_extractor = PortfolioExtractor()
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
        raw_html = page_data.get("raw_html") or ""
        h1 = page_data.get("h1", "")
        h2s = page_data.get("h2s", [])

        # 1. Dedicated Portfolio DOM Extraction (runs on raw HTML before text pruning)
        dom_candidates: List[Dict[str, Any]] = []
        if raw_html:
            try:
                dom_candidates = self.portfolio_extractor.extract_portfolio_candidates(
                    raw_html,
                    page_url=url,
                    page_title=title,
                    provider_domain=competitor_domain,
                    provider_brand=competitor_brand,
                )
            except Exception as pe_err:
                logger.warning("[PORTFOLIO_DOM] extraction error on %s: %s", url, pe_err)

        # 2. Multi-signal page classification
        page_meta = self.text_extractor.classify_page_relevance(
            url=url,
            title=title,
            text=text,
            h1=h1,
            h2s=h2s,
            raw_html=raw_html,
        )

        # If DOM found cards, promote to Client Portfolio page if score was marginal
        if dom_candidates and not page_meta["is_client_reference_page"]:
            page_meta["is_client_reference_page"] = True
            page_meta["page_category"] = "Client Portfolio"
            page_meta["relevance_score"] = max(page_meta.get("relevance_score", 0), 80)
            page_meta["indicators_found"].append(f"dom_portfolio_cards_override_{len(dom_candidates)}")

        if not page_meta["is_client_reference_page"] and not dom_candidates:
            logger.debug(
                "Page not a client reference page (category=%s, score=%d): %s",
                page_meta.get("page_category"),
                page_meta.get("relevance_score", 0),
                url,
            )
            return [], [], page_meta

        # Convert DOM candidates into structured reference format
        dom_references: List[Dict[str, Any]] = []
        for c in dom_candidates:
            dom_references.append({
                "company_name": c["candidate_name"],
                "company_website": c.get("client_website_url"),
                "client_name": c["candidate_name"],
                "client_website": c.get("client_website_url"),
                "relationship_type": c.get("relationship_type", "client_portfolio_reference"),
                "reference_type": c.get("relationship_type", "client_portfolio_reference"),
                "confidence": c.get("confidence_score", 0.9),
                "confidence_score": c.get("confidence_score", 0.9),
                "source_url": url,
                "evidence_quote": c.get("evidence_text") or f"Portfolio entry: {c['candidate_name']}",
                "evidence_snippet": c.get("evidence_text") or f"Portfolio entry: {c['candidate_name']}",
                "industry": c.get("industry"),
                "extraction_method": c.get("extraction_method", "portfolio_dom"),
                "image_url": c.get("image_url"),
                "section_heading": c.get("section_heading"),
            })

        # 3. Deterministic rich text extraction
        deterministic: List[Dict[str, Any]] = []
        if text and len(text.strip()) >= 50:
            deterministic = self.page_analyzer.analyze(text, url, title)

        # 4. NVIDIA augmentation if available
        ai_results: List[Dict[str, Any]] = []
        if await self.nvidia_client.is_available() and text:
            try:
                raw = await self.nvidia_client.extract_entities(text, url, title)
                if raw:
                    ai_results = raw
            except Exception as e:
                logger.warning("NVIDIA entity extraction error: %s", e)

        # 5. Merge results: DOM candidates have highest priority for company & external URLs
        merged = self._merge(dom_references, deterministic, ai_results, url)

        # 6. Strict multi-stage validation with competitor blacklist
        valid_references: List[Dict[str, Any]] = []
        rejected_candidates: List[Dict[str, Any]] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for ref in merged:
            ref["provider_id"] = provider_id
            ref["page_category"] = page_meta.get("page_category", "Client Portfolio")
            ref["collected_at"] = now_iso
            ref["verification_status"] = "pending_review"

            # Check evidence validity with competitor blacklist
            is_valid, rejection_reasons = self.evidence_validator.validate(
                ref,
                source_text=text or (ref.get("evidence_quote") or ""),
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
            "Extracted from %s: %d valid client references, %d rejected candidates (dom=%d, det=%d, ai=%d)",
            url, len(valid_references), len(rejected_candidates), len(dom_references), len(deterministic), len(ai_results),
        )
        return valid_references, rejected_candidates, page_meta

    def _merge(
        self,
        dom_refs: Optional[List[Dict]],
        det: Optional[List[Dict]],
        ai: Optional[List[Dict]],
        url: str,
    ) -> List[Dict]:
        """Merge DOM, deterministic, and AI results, prioritizing DOM evidence with exact outbound URLs."""
        by_key: Dict[str, Dict] = {}

        def identity_key(ref: Dict) -> str:
            person = " ".join(str(ref.get("person_name") or "").split()).casefold()
            company = " ".join(str(ref.get("company_name") or "").split()).casefold()

            if person:
                return f"person:{person}|company:{company}"
            if company:
                return f"comp:{company}"
            return ""

        # 1. Seed with high-fidelity DOM candidates
        for ref in (dom_refs or []):
            comp = ref.get("company_name") or ""
            key = f"comp:{comp}".lower()
            if key:
                by_key[key] = dict(ref)

        # 2. Layer in deterministic text extraction
        for ref in (det or []):
            person = ref.get("person_name")
            comp = ref.get("company_name")
            key = identity_key(ref)
            if not key:
                continue
            if key in by_key:
                # Fill missing fields without overwriting DOM website URL or quotes
                existing = by_key[key]
                if person and not existing.get("person_name"):
                    existing["person_name"] = person
                if not existing.get("designation") and ref.get("designation"):
                    existing["designation"] = ref["designation"]
                if not existing.get("industry") and ref.get("industry"):
                    existing["industry"] = ref["industry"]
            else:
                by_key[key] = dict(ref)

        # 3. Layer in AI extractions
        for ref in (ai or []):
            person = ref.get("person_name")
            comp = ref.get("company_name")
            key = identity_key(ref)
            if not key:
                continue
            if key in by_key:
                existing = by_key[key]
                for field in ("designation", "industry", "service_category"):
                    if not existing.get(field) and ref.get(field):
                        existing[field] = ref[field]
            else:
                by_key[key] = dict(ref)

        return list(by_key.values())
