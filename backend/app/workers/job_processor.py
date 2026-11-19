"""
Background Job Processor — Complete Pipeline.
- Multi-signal portfolio detection and dedicated HTML DOM card extraction.
- Company-first discovery, creation, and independent website enrichment.
- Public business contact extraction (emails, phones, forms, socials) with provenance.
- Optional decision-maker discovery without blocking company-level enrichment.
- Persistent event logging to `job_events` with real-time SSE broadcast.
- Structured data-quality metrics and comprehensive research report generation.
- Graceful resource cleanup, cancellation checking, and failure isolation.
"""
import asyncio
import inspect
import os
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Set
from bson import ObjectId

from app.database.connection import connect_to_mongo, close_mongo_connection, get_database
from app.discovery.discovery_manager import DiscoveryManager
from app.discovery.client_website_resolver import ClientWebsiteResolver
from app.crawler.crawler_manager import CrawlerManager
from app.extraction.client_classifier import ClientClassifier
from app.extraction.person_profile_extractor import PersonProfileExtractor
from app.crm.reference_service import ReferenceService
from app.crm.contact_service import ContactService
from app.crm.company_service import CompanyService
from app.crm.lead_service import LeadService
from app.enrichment.contact_enrichment_service import ContactEnrichmentService
from app.enrichment.company_enrichment_service import CompanyEnrichmentService
from app.utils.job_logger import log_job_event
from app.utils.url_utils import extract_domain
from app.discovery.url_normalizer import is_crawlable_content_url
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (worker) %(message)s",
)
logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MINUTES = 20
MAX_PAGES_PER_JOB = getattr(settings, "CRAWLER_MAX_PAGES_PER_JOB", 50)


def _err(stage: str, message: str, url: Optional[str] = None, err_type: str = "unknown", traceback_str: Optional[str] = None) -> Dict:
    res = {
        "stage": stage,
        "message": str(message)[:500],
        "error_type": err_type,
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if traceback_str:
        res["traceback"] = traceback_str
    return res


class JobProcessor:
    def __init__(self):
        self.worker_id = f"worker-{os.getpid()}-{int(datetime.now(timezone.utc).timestamp())}"
        self.discovery_manager = DiscoveryManager(max_pages=MAX_PAGES_PER_JOB)
        self.crawler_manager = CrawlerManager(max_pages=MAX_PAGES_PER_JOB)
        self.client_classifier = ClientClassifier()
        self.person_extractor = PersonProfileExtractor()
        self.enrichment_service = ContactEnrichmentService()
        self.company_enrichment_service = CompanyEnrichmentService()
        self.company_enricher = self.company_enrichment_service
        self.website_resolver = ClientWebsiteResolver()
        self.running = True

    async def is_job_cancelled(self, db, job_id: str) -> bool:
        """Actively checks if the job status in database has been marked cancelled."""
        try:
            job = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)}, {"status": 1})
            return bool(job and job.get("status") == "cancelled")
        except Exception:
            return False

    async def acquire_job(self, db) -> Optional[Dict[str, Any]]:
        lock_cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
        query = {
            "$or": [
                {"status": "pending"},
                {
                    "status": "running",
                    "locked_at": {"$lt": lock_cutoff},
                },
            ]
        }
        update = {
            "$set": {
                "status": "running",
                "current_stage": "discovering",
                "lock_key": self.worker_id,
                "locked_at": datetime.now(timezone.utc),
                "started_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        }
        job = await db.crawl_jobs.find_one_and_update(
            query, update, return_document=True,
        )
        return job

    async def _handle_cancellation(self, db, job_id: str, stage: str):
        """Cleanly releases worker lock and records cancellation event."""
        logger.info("[JOB] Job %s was cancelled during stage %s. Aborting worker execution.", job_id, stage)
        await self.crawler_manager.cleanup()
        now = datetime.now(timezone.utc)
        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "status": "cancelled",
                "current_stage": "cancelled",
                "lock_key": None,
                "locked_at": None,
                "completed_at": now,
                "cancelled_at": now,
                "updated_at": now,
            }},
        )
        await log_job_event(
            db, job_id, stage, "warning", "job_cancelled",
            f"Job was stopped cleanly due to cancellation during {stage}",
            metadata={"cancelled_at": now.isoformat()}
        )

    async def process_job(self, job: Dict[str, Any], db):
        job_id = str(job["_id"])
        provider_id = job.get("provider_id")
        start_url = job.get("starting_url") or job.get("target_url")
        job_type = job.get("job_type") or "full_research"

        # Auto-detect person profile workflow if URL contains biographical or person profile paths
        if job_type == "full_research" and start_url:
            path_l = start_url.lower()
            if any(seg in path_l for seg in ["/wiki/", "/person/", "/profile/", "/people/", "/author/", "/leadership/", "/executive/"]):
                job_type = "person_profile"
                logger.info("[JOB] Auto-detected person profile research workflow for %s", start_url)

        logger.info("[JOB] Processing %s | type=%s | provider=%s | url=%s", job_id, job_type, provider_id, start_url)

        if not start_url:
            await self._fail(db, job_id, _err("startup", "missing starting_url", err_type="config"))
            return

        # Check cancellation before starting
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "startup")
            return

        await log_job_event(db, job_id, "queued", "info", "job_started", f"Starting research job for {start_url}")

        errors: List[Dict] = []
        warnings: List[Dict] = []

        # ---------- Stage 1: URL discovery ----------
        page_limit = job.get("max_pages") or MAX_PAGES_PER_JOB
        discovered_urls: List[str] = []
        try:
            await self._stage(db, job_id, "discovering", 5)
            await log_job_event(db, job_id, "discovering", "info", "discovery_source_started", f"Starting discovery on {start_url} (limit: {page_limit} pages)")

            discovery = await self.discovery_manager.discover_all_urls(start_url, max_urls=page_limit)

            if await self.is_job_cancelled(db, job_id):
                await self._handle_cancellation(db, job_id, "discovering")
                return

            discovered_entries = discovery.get("discovered_urls", [])
            discovered_urls = [
                d["url"] for d in discovered_entries
                if isinstance(d, dict) and d.get("url") and is_crawlable_content_url(d.get("url"))
            ][:page_limit]

            if not discovered_urls and is_crawlable_content_url(start_url):
                discovered_urls = [start_url]

            for entry in discovered_entries[:10]:
                u = entry.get("url")
                src = entry.get("discovery_source", "unknown")
                cat = entry.get("page_category", "general")
                await log_job_event(
                    db, job_id, "discovering", "info", "url_discovered",
                    f"Discovered {u} via {src} [{cat}]",
                    url=u, metadata={"category": cat, "priority": entry.get("priority")}
                )

            await db.crawl_jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "max_pages": page_limit,
                    "pages_discovered": len(discovered_urls),
                    "pages_attempted": 0,
                    "pages_crawled": 0,
                    "pages_failed": 0,
                    "pages_skipped": 0,
                    "pages_analysed": 0,
                    "discovery_stats": discovery.get("sources_breakdown", {}),
                    "progress_pct": 20,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            await log_job_event(
                db, job_id, "discovering", "success", "discovery_source_completed",
                f"Discovery completed with {len(discovered_urls)} target URLs",
                metadata={"breakdown": discovery.get("sources_breakdown", {})}
            )
        except Exception as e:
            logger.exception("[DISCOVERY] failed")
            errors.append(_err("discovery", str(e), err_type="discovery"))
            await log_job_event(db, job_id, "discovering", "error", "discovery_source_failed", f"Discovery error: {e}")
            discovered_urls = [start_url] if is_crawlable_content_url(start_url) else []

        # Check cancellation before crawl
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-crawl")
            return

        # ---------- Stage 2: Crawl ----------
        crawled_pages: List[Dict] = []
        pages_attempted = 0
        pages_crawled = 0
        pages_failed = 0
        pages_skipped = 0
        try:
            await self._stage(db, job_id, "crawling", 25)
            await log_job_event(db, job_id, "crawling", "info", "crawl_started", f"Starting crawler on {len(discovered_urls)} URLs (max: {page_limit})")

            async def cancel_check():
                return await self.is_job_cancelled(db, job_id)

            crawled_pages = await self.crawler_manager.crawl_urls(
                discovered_urls,
                job_id=job_id,
                db=db,
                is_cancelled_fn=cancel_check,
                max_pages=page_limit,
            )

            if await self.is_job_cancelled(db, job_id):
                await self._handle_cancellation(db, job_id, "crawling")
                return

            success = [p for p in crawled_pages if p.get("status") == "success"]
            failed = [p for p in crawled_pages if p.get("status") == "failed"]
            skipped = [p for p in crawled_pages if p.get("status") == "skipped"]

            pages_attempted = len(crawled_pages)
            pages_crawled = len(success)
            pages_failed = len(failed)
            pages_skipped = len(skipped)

            await db.crawl_jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "pages_attempted": pages_attempted,
                    "pages_crawled": pages_crawled,
                    "pages_failed": pages_failed,
                    "pages_skipped": pages_skipped,
                    "progress_pct": 45,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )

            for p in failed:
                errors.append(_err(
                    "crawling", p.get("error") or "unknown",
                    url=p.get("url"), err_type=p.get("error_type") or "crawl",
                ))
            for p in skipped:
                warnings.append(_err(
                    "crawling", p.get("error") or "skipped",
                    url=p.get("url"), err_type=p.get("error_type") or "skip",
                ))

            await log_job_event(
                db, job_id, "crawling", "success", "crawl_completed",
                f"Crawl completed: {pages_crawled} successful, {pages_failed} failed, {pages_skipped} skipped"
            )

            if not success:
                raise RuntimeError(
                    f"No pages crawled successfully. First error: {errors[0]['message'] if errors else 'unknown'}"
                )
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("[CRAWLER] fatal error for job %s:\n%s", job_id, tb)
            err_dict = _err("crawling", f"{type(e).__name__}: {str(e)}", err_type="crawl_fatal", traceback_str=tb)
            errors.append(err_dict)
            await log_job_event(
                db, job_id, "crawling", "error", "crawl_failed",
                f"Crawl fatal error: {type(e).__name__}: {e}",
                metadata={"traceback": tb[-1000:], "error_type": "crawl_fatal"}
            )
            await self._finish(db, job_id, "failed", errors, warnings, 0, 0, 0, 0)
            return

        # Check cancellation before page persistence
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "persist_pages")
            return

        # ---------- Stage 3: Persist pages ----------
        crawl_page_ids = []
        try:
            for page in crawled_pages:
                if page.get("status") != "success":
                    continue
                doc = {
                    "job_id": job_id,
                    "provider_id": provider_id,
                    "url": page.get("url"),
                    "page_title": page.get("page_title", ""),
                    "word_count": page.get("word_count", 0),
                    "extraction_method": page.get("extraction_method", "httpx"),
                    "javascript_rendered": page.get("javascript_rendered", False),
                    "http_status": page.get("http_status"),
                    "public_emails": page.get("public_emails", []),
                    "social_profiles": page.get("social_profiles", []),
                    "main_text": (page.get("main_text") or "")[:20000],
                    "raw_html": (page.get("raw_html") or "")[:500000],
                    "crawled_at": datetime.now(timezone.utc),
                }
                insert_res = db.crawl_pages.insert_one(doc)
                r = await insert_res if inspect.isawaitable(insert_res) else insert_res
                if hasattr(r, "inserted_id"):
                    crawl_page_ids.append(str(r.inserted_id))
        except Exception as e:
            logger.exception("[PAGES] persist failed")
            warnings.append(_err("persist_pages", str(e), err_type="mongo"))

        # Check cancellation before extraction
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-extract")
            return

        # ---------- Stage 4: Extraction ----------
        await self._stage(db, job_id, "extracting", 50)
        await log_job_event(db, job_id, "extracting", "info", "extraction_started", "Starting client reference & portfolio DOM extraction")

        reference_service = ReferenceService(db)
        contact_service = ContactService(db)
        company_service = CompanyService(db)
        lead_service = LeadService(db)

        pages_analysed = 0
        portfolio_pages_count = 0
        candidates_detected = 0
        valid_client_references = 0
        company_only_references = 0
        featured_personalities = 0
        collaborators = 0
        ordinary_mentions = 0
        rejected_false_matches = 0
        pending_verification = 0
        contacts_created = 0
        companies_created = 0
        leads_created = 0
        confidence_bands = {"high": 0, "medium": 0, "low": 0}
        rejected_sample: List[Dict[str, Any]] = []
        all_job_contact_ids: List[str] = []
        discovered_company_ids: List[str] = []
        discovered_client_references: List[Dict[str, Any]] = []
        discovered_person_profiles: List[Dict[str, Any]] = []
        page_diagnostics: List[Dict[str, Any]] = []

        competitor_domain = None
        competitor_brand = None
        if provider_id:
            try:
                prov_doc = await db.providers.find_one({"_id": ObjectId(provider_id)})
                if prov_doc:
                    competitor_domain = prov_doc.get("domain") or extract_domain(prov_doc.get("website", ""))
                    competitor_brand = prov_doc.get("name")
            except Exception:
                pass
        if not competitor_domain and start_url:
            competitor_domain = extract_domain(start_url)

        for page in crawled_pages:
            if await self.is_job_cancelled(db, job_id):
                await self._handle_cancellation(db, job_id, "extracting")
                return

            if page.get("status") != "success":
                continue
            pages_analysed += 1
            page_url = page.get("url") or ""

            # Workflow B: Person Profile Extraction
            try:
                is_person, p_conf, p_reason = self.person_extractor.is_person_profile_page(page)
                if is_person or job_type == "person_profile":
                    p_prof = self.person_extractor.extract_profile(page)
                    if p_prof and p_prof.get("person_name"):
                        if not any(dp["person_name"].lower() == p_prof["person_name"].lower() for dp in discovered_person_profiles):
                            discovered_person_profiles.append(p_prof)
                            await log_job_event(
                                db, job_id, "extracting", "success", "person_profile_extracted",
                                f"Identified person profile: {p_prof['person_name']} ({p_prof.get('designation')}) [conf={p_prof.get('confidence_score')}]",
                                url=page_url,
                                metadata={"person_name": p_prof["person_name"], "confidence": p_prof.get("confidence_score")}
                            )
                page_diagnostics.append({
                    "url": page_url,
                    "is_person_profile": is_person,
                    "person_confidence": p_conf,
                    "detection_reason": p_reason,
                    "emails_found": len(page.get("public_emails") or []),
                    "socials_found": len(page.get("social_profiles") or []),
                    "status": "analyzed"
                })
            except Exception as pe_err:
                logger.warning("[PERSON_EXTRACTION] error for %s: %s", page_url, pe_err)

            # Workflow A: Portfolio & Client Reference Extraction
            try:
                refs, rejected, page_meta = await self.client_classifier.process_page_detailed(
                    page, provider_id, competitor_domain=competitor_domain, competitor_brand=competitor_brand
                )
                if page_meta.get("is_client_reference_page"):
                    portfolio_pages_count += 1
                    await log_job_event(
                        db, job_id, "extracting", "info", "portfolio_page_detected",
                        f"Detected {page_meta.get('page_category')} on {page_url} (score={page_meta.get('relevance_score')})",
                        url=page_url,
                        metadata=page_meta
                    )
            except Exception as e:
                logger.exception("[EXTRACTION] error for %s", page.get("url"))
                warnings.append(_err("extraction", str(e), url=page.get("url"), err_type="extract"))
                continue

            candidates_detected += len(refs) + len(rejected)
            rejected_false_matches += len(rejected)

            for r in rejected:
                cand_name = r.get("person_name") or r.get("company_name") or "unknown"
                if len(rejected_sample) < 50:
                    rejected_sample.append({
                        "candidate_name": cand_name,
                        "rejection_reasons": r.get("rejection_reasons", []),
                        "source_url": r.get("source_url"),
                        "evidence_quote": (r.get("evidence_quote") or "")[:200],
                    })
                await log_job_event(
                    db, job_id, "extracting", "warning", "candidate_rejected",
                    f"Rejected candidate: {cand_name} ({', '.join(r.get('rejection_reasons', []))})",
                    url=r.get("source_url")
                )

            for ref in refs:
                try:
                    rel = ref.get("relationship_type", "client_portfolio_reference")
                    conf = float(ref.get("confidence", 0.8))
                    if conf >= 0.8:
                        confidence_bands["high"] += 1
                    elif conf >= 0.6:
                        confidence_bands["medium"] += 1
                    else:
                        confidence_bands["low"] += 1

                    if not ref.get("person_name") and ref.get("company_name"):
                        company_only_references += 1
                    if rel == "featured_personality":
                        featured_personalities += 1
                    elif rel == "collaborator":
                        collaborators += 1
                    elif rel == "ordinary_mention":
                        ordinary_mentions += 1

                    cand_name = ref.get("company_name") or ref.get("person_name") or "client"
                    await log_job_event(
                        db, job_id, "extracting", "info", "candidate_detected",
                        f"Detected client: {cand_name} ({rel}, conf={conf})",
                        url=ref.get("source_url")
                    )

                    # 1. Company Creation & Persistence
                    # A person-only reference must not create a fake company.
                    company_id = None
                    comp_name = ref.get("company_name") or ref.get("client_name")
                    comp_website = (
                        ref.get("company_website")
                        or ref.get("client_website")
                        or ref.get("verified_website")
                        or ref.get("client_url")
                        or ref.get("website")
                    )

                    if comp_name:
                        comp_data = {
                            "name": comp_name,
                            "website": comp_website,
                            "industry": ref.get("industry"),
                            "source": "portfolio_intelligence",
                            "verification_status": "pending_review",
                        }
                        comp = await company_service.create(comp_data)
                        company_id = comp.get("id")

                        if company_id and comp_website:
                            await db.companies.update_one(
                                {"_id": ObjectId(company_id)},
                                {"$set": {"website": comp_website}}
                            )

                        if company_id and company_id not in discovered_company_ids:
                            discovered_company_ids.append(company_id)

                        if comp.get("created", False):
                            companies_created += 1
                            await log_job_event(
                                db, job_id, "extracting", "success",
                                "new_crm_record_saved",
                                f"Created company CRM record: {comp_name} ({comp_website or 'no website yet'})"
                            )

                    # 2. Persist the reference, including person-only evidence.
                    ref["company_id"] = company_id
                    ref["provider_id"] = provider_id
                    ref["job_id"] = job_id

                    if not comp_name and not ref.get("person_name"):
                        warnings.append(_err(
                            "crm",
                            "Reference skipped because it has no person or company identity",
                            url=ref.get("source_url"),
                            err_type="crm",
                        ))
                        continue

                    ref_doc = await reference_service.create(ref)
                    reference_created = ref_doc.get("created", True)

                    if reference_created:
                        valid_client_references += 1
                        pending_verification += 1

                    ref_id = ref_doc.get("id")
                    if ref_id and not any(
                        item.get("id") == ref_id
                        for item in discovered_client_references
                    ):
                        discovered_client_references.append(ref_doc)

                    # Update company's source references list.
                    if company_id and ref_id:
                        await db.companies.update_one(
                            {"_id": ObjectId(company_id)},
                            {"$addToSet": {"source_references": ref_id}},
                        )

                    # 3. Create/update a contact when a genuine person exists.
                    person_name = ref.get("person_name")

                    if (
                        person_name
                        and person_name.strip().casefold()
                        != (comp_name or "").strip().casefold()
                    ):
                        contact, was_new = await contact_service.create({
                            "full_name": person_name,
                            "designation": ref.get("designation"),
                            "company_id": company_id,
                            "company_name": comp_name,
                            "contact_verification_status": "discovered",
                            "source_references": [ref_id] if ref_id else [],
                        })

                        contact_id = contact.get("id")

                        if contact_id and contact_id not in all_job_contact_ids:
                            all_job_contact_ids.append(contact_id)

                        if was_new:
                            contacts_created += 1
                            await log_job_event(
                                db, job_id, "extracting", "success",
                                "contact_found",
                                f"Discovered person contact: {person_name} ({comp_name or 'company not established'})"
                            )

                        # Do not create leads for person-only references.
                        # For company-associated contacts, LeadService handles deduplication.
                        if company_id and contact_id:
                            lead_res = await lead_service.create(
                                contact_id=contact_id,
                                company_id=company_id,
                                lead_source=provider_id,
                                initial_stage="discovered",
                            )

                            if lead_res.get("created", False):
                                leads_created += 1

                except Exception as e:
                    logger.exception("[CRM] error creating record")
                    warnings.append(_err("crm", str(e), url=ref.get("source_url"), err_type="crm"))

        # Process Discovered Person Profiles into CRM (Workflow B)
        for p_profile in discovered_person_profiles:
            try:
                target_name = p_profile["person_name"]
                p_comp_name = p_profile.get("company_name")
                p_desig = p_profile.get("designation")
                p_emails = p_profile.get("public_emails", [])
                p_phones = p_profile.get("public_phones", [])
                p_socials = p_profile.get("social_profiles", [])

                linkedin_url = None
                if isinstance(p_socials, list):
                    for sp in p_socials:
                        if isinstance(sp, dict) and sp.get("platform") == "linkedin":
                            linkedin_url = sp.get("url")
                            break
                elif isinstance(p_socials, dict):
                    linkedin_url = p_socials.get("linkedin")

                p_company_id = None
                if p_comp_name:
                    comp_res = await company_service.create({
                        "name": p_comp_name,
                        "industry": "Professional Services",
                    })
                    p_company_id = comp_res.get("id")
                    if p_company_id and p_company_id not in discovered_company_ids:
                        discovered_company_ids.append(p_company_id)
                    if comp_res.get("created", False):
                        companies_created += 1

                contact, was_new = await contact_service.create({
                    "full_name": target_name,
                    "designation": p_desig or "Executive / Profile",
                    "company_id": p_company_id,
                    "company_name": p_comp_name,
                    "contact_verification_status": "discovered",
                    "email": p_emails[0] if p_emails else None,
                    "phone": p_phones[0] if p_phones else None,
                    "linkedin_url": linkedin_url,
                    "social_profiles": p_socials,
                    "bio_summary": p_profile.get("bio_summary"),
                })
                contact_id = contact.get("id")
                if contact_id and contact_id not in all_job_contact_ids:
                    all_job_contact_ids.append(contact_id)
                if was_new:
                    contacts_created += 1
                    lead_res = await lead_service.create(
                        contact_id=contact_id,
                        company_id=p_company_id,
                        lead_source=provider_id or "website_intelligence",
                        initial_stage="discovered",
                    )
                    if lead_res.get("created", False):
                        leads_created += 1
            except Exception as p_crm_err:
                logger.exception("[CRM] Error creating person profile record: %s", p_crm_err)

        # Check cancellation before company enrichment
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-company-enrichment")
            return

        # ---------- Stage 5: Company Website Resolution & Enrichment ----------
        companies_enriched_count = 0
        companies_without_website_count = 0
        companies_without_contacts_count = 0
        total_emails_found = 0
        total_phones_found = 0
        total_forms_found = 0
        total_socials_found = 0
        total_decision_makers_found = 0

        if discovered_company_ids:
            await self._stage(db, job_id, "enriching_companies", 70)
            await log_job_event(
                db, job_id, "enriching_companies", "info", "company_enrichment_started",
                f"Starting company website crawling & business contact extraction for {len(discovered_company_ids)} companies"
            )

            for cid in discovered_company_ids:
                if await self.is_job_cancelled(db, job_id):
                    await self._handle_cancellation(db, job_id, "enriching_companies")
                    return

                try:
                    en_res = await self.company_enrichment_service.enrich_company(db, cid)
                    companies_enriched_count += 1
                    c_name = en_res.get("company_name", "Company")
                    n_em = en_res.get("business_emails", 0)
                    n_ph = en_res.get("business_phones", 0)
                    n_fm = en_res.get("contact_forms", 0)
                    n_soc = en_res.get("social_links", 0)
                    n_dm = en_res.get("decision_makers_found", 0)

                    total_emails_found += n_em
                    total_phones_found += n_ph
                    total_forms_found += n_fm
                    total_socials_found += n_soc
                    total_decision_makers_found += n_dm

                    if en_res.get("status") == "no_website":
                        companies_without_website_count += 1
                        msg = f"{c_name}: No verified website available to crawl"
                    elif en_res.get("status") == "no_contacts_found":
                        companies_without_contacts_count += 1
                        msg = f"{c_name}: Crawled {en_res.get('website')}, no public email/phone found"
                    else:
                        msg = f"{c_name}: Found {n_em} email(s), {n_ph} phone(s), {n_fm} form(s), {n_soc} social(s)"

                    if en_res.get("contacts_created", 0) > 0:
                        contacts_created += en_res["contacts_created"]

                    await log_job_event(
                        db, job_id, "enriching_companies", "info", "company_enriched",
                        msg,
                        metadata={
                            "company_id": cid,
                            "company_name": c_name,
                            "website": en_res.get("website"),
                            "emails": n_em,
                            "phones": n_ph,
                            "forms": n_fm,
                            "decision_makers": n_dm,
                        }
                    )
                except Exception as ce_err:
                    logger.warning("[COMPANY_ENRICH] Error on company %s: %s", cid, ce_err)
                    warnings.append(_err("company_enrichment", str(ce_err), err_type="enrich_company"))

        # Check cancellation before contact enrichment
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-contact-enrichment")
            return

        # ---------- Stage 6: Person-Level Enrichment ----------
        enrichment_metrics = {
            "total_contacts_enriched": 0,
            "direct_emails_found": 0,
            "direct_phones_found": 0,
            "generic_emails_found": 0,
            "company_phones_found": 0,
            "contact_forms_found": total_forms_found,
            "no_public_contacts_found": 0,
        }

        # Enrich discovered person profiles
        for p_prof in discovered_person_profiles:
            try:
                enriched_p = await self.enrichment_service.enrich_person_profile(p_prof, db)
                p_prof.update(enriched_p)
            except Exception as e:
                logger.warning("[ENRICHMENT] Person profile enrichment error: %s", e)

        if all_job_contact_ids:
            await self._stage(db, job_id, "enriching_contacts", 85)
            logger.info("[ENRICHMENT] Starting contact enrichment for %d contacts", len(all_job_contact_ids))
            for cid in all_job_contact_ids:
                if await self.is_job_cancelled(db, job_id):
                    await self._handle_cancellation(db, job_id, "enriching_contacts")
                    return
                try:
                    en_res = await self.enrichment_service.enrich_contact(db, cid)
                    enrichment_metrics["total_contacts_enriched"] += 1
                    enrichment_metrics["direct_emails_found"] += en_res.get("direct_emails", 0)
                    enrichment_metrics["direct_phones_found"] += en_res.get("direct_phones", 0)
                    enrichment_metrics["generic_emails_found"] += en_res.get("generic_emails", 0)
                    enrichment_metrics["company_phones_found"] += en_res.get("company_phones", 0)
                    if en_res.get("status") == "no_public_contacts_found":
                        enrichment_metrics["no_public_contacts_found"] += 1
                except Exception as en_err:
                    logger.warning("[ENRICHMENT] error on contact %s: %s", cid, en_err)

        # Check cancellation before report generation
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-report")
            return

        # Complete Structured Data Quality Metrics
        data_quality_metrics = {
            "pages_processed": len([p for p in crawled_pages if p.get("status") == "success"]),
            "pages_analysed": pages_analysed,
            "portfolio_pages_processed": portfolio_pages_count,
            "portfolio_cards_detected": candidates_detected,
            "company_candidates_extracted": candidates_detected,
            "valid_client_references": valid_client_references,
            "company_only_references": company_only_references,
            "featured_personalities": featured_personalities,
            "collaborators": collaborators,
            "ordinary_mentions": ordinary_mentions,
            "rejected_candidates": rejected_false_matches,
            "pending_verification": pending_verification,
            "companies_created": companies_created,
            "companies_enriched": companies_enriched_count,
            "companies_without_website": companies_without_website_count,
            "companies_without_public_contacts": companies_without_contacts_count,
            "business_emails_found": total_emails_found,
            "business_phones_found": total_phones_found,
            "contact_forms_found": total_forms_found,
            "decision_makers_found": total_decision_makers_found,
            "contacts_created": contacts_created,
            "leads_created": leads_created,
            "confidence_distribution": confidence_bands,
            "enrichment_metrics": enrichment_metrics,
        }

        # Determine report_mode
        report_mode = "provider"
        if job_type == "person_profile" or (discovered_person_profiles and valid_client_references == 0):
            report_mode = "person"
        elif discovered_person_profiles and valid_client_references > 0:
            report_mode = "hybrid"

        primary_profile = discovered_person_profiles[0] if discovered_person_profiles else None

        # ---------- Stage 7: Report ----------
        await self._stage(db, job_id, "generating_report", 95)
        try:
            await self._generate_report(
                db, job_id, provider_id, start_url, crawled_pages,
                valid_client_references, data_quality_metrics, rejected_sample,
                job_type=job_type,
                discovered_person_profiles=discovered_person_profiles,
                page_diagnostics=page_diagnostics,
                discovered_company_ids=discovered_company_ids,
                max_pages=page_limit,
                pages_discovered=len(discovered_urls),
                pages_attempted=pages_attempted,
                pages_crawled=pages_crawled,
                pages_failed=pages_failed,
                pages_skipped=pages_skipped,
                pages_analysed=pages_analysed,
            )
            await log_job_event(db, job_id, "generating_report", "success", "report_generated", "Research report generated successfully")
        except Exception as e:
            logger.exception("[REPORT] failed")
            warnings.append(_err("report", str(e), err_type="report"))

        # Final check if job was cancelled
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "finalizing")
            return

        # ---------- Final Completion ----------
        final_status = "completed" if not warnings and not errors else "completed_with_warnings"
        await self._finish(
            db, job_id, final_status, errors, warnings,
            valid_client_references, contacts_created, companies_created, leads_created,
            data_quality_metrics=data_quality_metrics,
            job_type=job_type,
            report_mode=report_mode,
            person_profile=primary_profile,
            pages_discovered=len(discovered_urls),
            pages_attempted=pages_attempted,
            pages_crawled=pages_crawled,
            pages_failed=pages_failed,
            pages_skipped=pages_skipped,
            pages_analysed=pages_analysed,
            max_pages=page_limit,
        )
        await log_job_event(
            db, job_id, "completed", "success", "job_completed",
            f"Research complete: {valid_client_references} client references, {companies_enriched_count} companies enriched ({total_emails_found} emails, {total_phones_found} phones), {leads_created} leads created"
        )
        logger.info(
            "[JOB] %s done. refs=%d companies=%d (%d enriched) emails=%d phones=%d contacts=%d leads=%d mode=%s",
            job_id, valid_client_references, companies_created, companies_enriched_count,
            total_emails_found, total_phones_found, contacts_created, leads_created, report_mode
        )

    async def _stage(self, db, job_id: str, stage: str, progress: int):
        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "current_stage": stage,
                "progress_pct": progress,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

    async def _finish(self, db, job_id, status, errors, warnings,
                      refs, contacts, companies, leads, data_quality_metrics: Optional[Dict] = None,
                      job_type: str = "full_research", report_mode: str = "provider",
                      person_profile: Optional[Dict] = None,
                      pages_discovered: Optional[int] = None,
                      pages_attempted: Optional[int] = None,
                      pages_crawled: Optional[int] = None,
                      pages_failed: Optional[int] = None,
                      pages_skipped: Optional[int] = None,
                      pages_analysed: Optional[int] = None,
                      max_pages: Optional[int] = None):
        now = datetime.now(timezone.utc)
        update_doc = {
            "status": status,
            "current_stage": "completed" if status.startswith("completed") else "failed",
            "progress_pct": 100 if status.startswith("completed") else 0,
            "errors": errors[-30:],
            "warnings": warnings[-30:],
            "references_found": refs,
            "contacts_created": contacts,
            "companies_created": companies,
            "leads_created": leads,
            "job_type": job_type,
            "report_mode": report_mode,
            "lock_key": None,
            "locked_at": None,
            "completed_at": now,
            "updated_at": now,
        }
        if pages_discovered is not None:
            update_doc["pages_discovered"] = pages_discovered
        if pages_attempted is not None:
            update_doc["pages_attempted"] = pages_attempted
        if pages_crawled is not None:
            update_doc["pages_crawled"] = pages_crawled
        if pages_failed is not None:
            update_doc["pages_failed"] = pages_failed
        if pages_skipped is not None:
            update_doc["pages_skipped"] = pages_skipped
        if pages_analysed is not None:
            update_doc["pages_analysed"] = pages_analysed
        if max_pages is not None:
            update_doc["max_pages"] = max_pages
        if person_profile:
            update_doc["person_profile"] = person_profile
        if data_quality_metrics:
            update_doc["data_quality_metrics"] = data_quality_metrics

        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_doc},
        )

    async def _fail(self, db, job_id, error: Dict):
        now = datetime.now(timezone.utc)
        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "status": "failed",
                "current_stage": "failed",
                "lock_key": None,
                "locked_at": None,
                "errors": [error],
                "completed_at": now,
                "updated_at": now,
            }},
        )
        await log_job_event(
            db, job_id, "failed", "error", "job_failed",
            f"Job failed: {error.get('message', 'unknown error')}"
        )

    async def _generate_report(self, db, job_id, provider_id, start_url,
                               pages: List[Dict], references_found: int,
                               data_quality_metrics: Optional[Dict] = None,
                               rejected_sample: Optional[List[Dict]] = None,
                               job_type: str = "full_research",
                               discovered_person_profiles: Optional[List[Dict]] = None,
                               page_diagnostics: Optional[List[Dict]] = None,
                               discovered_company_ids: Optional[List[str]] = None,
                               max_pages: Optional[int] = None,
                               pages_discovered: Optional[int] = None,
                               pages_attempted: Optional[int] = None,
                               pages_crawled: Optional[int] = None,
                               pages_failed: Optional[int] = None,
                               pages_skipped: Optional[int] = None,
                               pages_analysed: Optional[int] = None):
        success_pages = [p for p in pages if p.get("status") == "success"]
        failed_pages = [p for p in pages if p.get("status") == "failed"]

        # Fetch all enriched companies for the report
        enriched_companies = []
        if discovered_company_ids:
            try:
                comp_find = db.companies.find({
                    "_id": {"$in": [ObjectId(cid) for cid in discovered_company_ids if ObjectId.is_valid(cid)]}
                })
                if hasattr(comp_find, "to_list"):
                    comp_fut = comp_find.to_list(100)
                    c_docs = await comp_fut if inspect.isawaitable(comp_fut) else []
                else:
                    c_docs = []
                for cd in c_docs:
                    if isinstance(cd, dict):
                        cd["id"] = str(cd.pop("_id", ""))
                        for dt_field in ("created_at", "updated_at", "last_enriched_at"):
                            if cd.get(dt_field) and hasattr(cd[dt_field], "isoformat"):
                                cd[dt_field] = cd[dt_field].isoformat()
                        enriched_companies.append(cd)
            except Exception as ce:
                logger.warning("[REPORT] Error fetching companies for report: %s", ce)

        socials: Dict[str, List[str]] = {}
        for p in success_pages:
            for sp in (p.get("social_profiles") or []):
                platform = sp.get("platform")
                url = sp.get("url")
                if platform and url:
                    socials.setdefault(platform, [])
                    if url not in socials[platform]:
                        socials[platform].append(url)

        # Merge socials from discovered_person_profiles
        for p_prof in (discovered_person_profiles or []):
            for sp in (p_prof.get("social_profiles") or []):
                platform = sp.get("platform")
                url = sp.get("url")
                if platform and url:
                    socials.setdefault(platform, [])
                    if url not in socials[platform]:
                        socials[platform].append(url)

        emails = set()
        for p in success_pages:
            for e in (p.get("public_emails") or []):
                emails.add(e)
        for p_prof in (discovered_person_profiles or []):
            for e in (p_prof.get("public_emails") or []):
                emails.add(e)

        # Merge emails from enriched companies
        for comp in enriched_companies:
            for ch in (comp.get("public_contact_channels") or []):
                if ch.get("type") == "email" and ch.get("value"):
                    emails.add(ch["value"])

        report_mode = "provider"
        if job_type == "person_profile" or (discovered_person_profiles and references_found == 0):
            report_mode = "person"
        elif discovered_person_profiles and references_found > 0:
            report_mode = "hybrid"

        primary_profile = discovered_person_profiles[0] if discovered_person_profiles else None

        report = {
            "job_id": job_id,
            "provider_id": provider_id,
            "starting_url": start_url,
            "job_type": job_type,
            "report_mode": report_mode,
            "status": "completed",
            "max_pages": max_pages,
            "pages_discovered": pages_discovered if pages_discovered is not None else len(pages),
            "pages_attempted": pages_attempted if pages_attempted is not None else len(pages),
            "pages_crawled": pages_crawled if pages_crawled is not None else len(success_pages),
            "pages_processed": len(success_pages),
            "pages_failed": pages_failed if pages_failed is not None else len(failed_pages),
            "pages_skipped": pages_skipped if pages_skipped is not None else 0,
            "pages_analysed": pages_analysed if pages_analysed is not None else len(success_pages),
            "references_found": references_found,
            "companies": enriched_companies,
            "person_profile": primary_profile,
            "person_profiles": discovered_person_profiles or [],
            "page_diagnostics": page_diagnostics or [],
            "data_quality_metrics": data_quality_metrics or {},
            "enrichment_summary": (data_quality_metrics or {}).get("enrichment_metrics", {}),
            "rejected_candidates": rejected_sample or [],
            "social_media_profiles": socials,
            "public_emails_discovered": sorted(emails),
            "failed_urls": [
                {"url": p.get("url"), "error": p.get("error")}
                for p in failed_pages
            ],
            "generated_at": datetime.now(timezone.utc),
        }
        await db.research_reports.replace_one(
            {"job_id": job_id}, report, upsert=True,
        )

    async def run(self):
        logger.info("Starting Background Job Processor [%s]", self.worker_id)
        await connect_to_mongo()
        db = get_database()

        while self.running:
            try:
                job = await self.acquire_job(db)
                if job:
                    try:
                        await self.process_job(job, db)
                    except Exception as e:
                        logger.exception("[JOB] unhandled exception")
                        await self._fail(db, str(job["_id"]),
                                         _err("worker", str(e), err_type="worker_fatal"))
                else:
                    await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker loop error: %s", e)
                await asyncio.sleep(3)

        await close_mongo_connection()
        logger.info("Worker shut down.")


async def main():
    processor = JobProcessor()
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
