"""
Background Job Processor — Enhanced.
- Full cancellation checking across all execution stages and page iterations.
- Persistent event logging to `job_events` with real-time SSE broadcast.
- Graceful resource and browser cleanup on cancel or error.
- Preservation of partial results upon cancellation.
- Atomic distributed locking with stale-lock reclamation (ignoring cancelled jobs).
"""
import asyncio
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from bson import ObjectId

from app.database.connection import connect_to_mongo, close_mongo_connection, get_database
from app.discovery.discovery_manager import DiscoveryManager
from app.crawler.crawler_manager import CrawlerManager
from app.extraction.client_classifier import ClientClassifier
from app.crm.reference_service import ReferenceService
from app.crm.contact_service import ContactService
from app.crm.company_service import CompanyService
from app.crm.lead_service import LeadService
from app.enrichment.contact_enrichment_service import ContactEnrichmentService
from app.utils.job_logger import log_job_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (worker) %(message)s",
)
logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MINUTES = 20
MAX_PAGES_PER_JOB = 30


def _err(stage: str, message: str, url: Optional[str] = None, err_type: str = "unknown") -> Dict:
    return {
        "stage": stage,
        "message": str(message)[:500],
        "error_type": err_type,
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class JobProcessor:
    def __init__(self):
        self.worker_id = f"worker-{os.getpid()}-{int(datetime.now(timezone.utc).timestamp())}"
        self.discovery_manager = DiscoveryManager(max_pages=MAX_PAGES_PER_JOB)
        self.crawler_manager = CrawlerManager(max_pages=MAX_PAGES_PER_JOB)
        self.client_classifier = ClientClassifier()
        self.enrichment_service = ContactEnrichmentService()
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
        # Never acquire cancelled, completed, or failed jobs
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

        logger.info("[JOB] Processing %s | provider=%s | url=%s", job_id, provider_id, start_url)

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
        discovered_urls: List[str] = []
        try:
            await self._stage(db, job_id, "discovering", 5)
            await log_job_event(db, job_id, "discovering", "info", "discovery_source_started", f"Starting discovery on {start_url}")

            discovery = await self.discovery_manager.discover_all_urls(start_url)

            # Check cancellation after discovery
            if await self.is_job_cancelled(db, job_id):
                await self._handle_cancellation(db, job_id, "discovering")
                return

            discovered_entries = discovery.get("discovered_urls", [])
            discovered_urls = [
                d["url"] for d in discovered_entries
                if isinstance(d, dict) and d.get("url")
            ][:MAX_PAGES_PER_JOB]

            if not discovered_urls:
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
                    "pages_discovered": len(discovered_urls),
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
            discovered_urls = [start_url]

        # Check cancellation before crawl
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-crawl")
            return

        # ---------- Stage 2: Crawl ----------
        crawled_pages: List[Dict] = []
        try:
            await self._stage(db, job_id, "crawling", 25)
            await log_job_event(db, job_id, "crawling", "info", "crawl_started", f"Starting crawler on {len(discovered_urls)} URLs")

            async def cancel_check():
                return await self.is_job_cancelled(db, job_id)

            crawled_pages = await self.crawler_manager.crawl_urls(
                discovered_urls,
                job_id=job_id,
                db=db,
                is_cancelled_fn=cancel_check,
            )

            # Check if cancelled during crawl
            if await self.is_job_cancelled(db, job_id):
                await self._handle_cancellation(db, job_id, "crawling")
                return

            success = [p for p in crawled_pages if p.get("status") == "success"]
            failed = [p for p in crawled_pages if p.get("status") == "failed"]
            skipped = [p for p in crawled_pages if p.get("status") == "skipped"]

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
                f"Crawl completed: {len(success)} successful, {len(failed)} failed, {len(skipped)} skipped"
            )

            if not success:
                raise RuntimeError(
                    f"No pages crawled successfully. First error: {errors[0]['message'] if errors else 'unknown'}"
                )
        except Exception as e:
            logger.exception("[CRAWLER] fatal")
            errors.append(_err("crawling", str(e), err_type="crawl_fatal"))
            await log_job_event(db, job_id, "crawling", "error", "crawl_failed", f"Crawl fatal error: {e}")
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
                    "crawled_at": datetime.now(timezone.utc),
                }
                r = await db.crawl_pages.insert_one(doc)
                crawl_page_ids.append(str(r.inserted_id))
        except Exception as e:
            logger.exception("[PAGES] persist failed")
            warnings.append(_err("persist_pages", str(e), err_type="mongo"))

        # Check cancellation before extraction
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-extract")
            return

        # ---------- Stage 4: Extraction ----------
        await self._stage(db, job_id, "extracting", 60)
        await log_job_event(db, job_id, "extracting", "info", "extraction_started", "Starting client reference extraction")

        reference_service = ReferenceService(db)
        contact_service = ContactService(db)
        company_service = CompanyService(db)
        lead_service = LeadService(db)

        pages_analysed = 0
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

        for page in crawled_pages:
            # Check cancellation between page extractions
            if await self.is_job_cancelled(db, job_id):
                await self._handle_cancellation(db, job_id, "extracting")
                return

            if page.get("status") != "success":
                continue
            pages_analysed += 1
            try:
                refs, rejected, page_meta = await self.client_classifier.process_page_detailed(page, provider_id)
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
                    f"Rejected false match: {cand_name} ({', '.join(r.get('rejection_reasons', []))})",
                    url=r.get("source_url")
                )

            for ref in refs:
                try:
                    rel = ref.get("relationship_type", "unclear_relationship")
                    conf = float(ref.get("confidence", 0.5))
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

                    cand_name = ref.get("person_name") or ref.get("company_name") or "client"
                    await log_job_event(
                        db, job_id, "extracting", "info", "candidate_detected",
                        f"Detected candidate: {cand_name} ({rel}, conf={conf})",
                        url=ref.get("source_url")
                    )

                    # Deduplication check
                    existing_query: Dict[str, Any] = {
                        "provider_id": provider_id,
                        "source_url": ref.get("source_url"),
                    }
                    if ref.get("person_name"):
                        existing_query["person_name"] = ref.get("person_name")
                    else:
                        existing_query["company_name"] = ref.get("company_name")

                    existing = await db.provider_client_references.find_one(existing_query)
                    if existing:
                        await log_job_event(
                            db, job_id, "extracting", "info", "duplicate_candidate_ignored",
                            f"Ignored duplicate candidate: {cand_name}",
                            url=ref.get("source_url")
                        )
                        continue

                    ref_doc = await reference_service.create(ref)
                    valid_client_references += 1
                    pending_verification += 1

                    # Company creation
                    company_id = None
                    if ref.get("company_name"):
                        comp_data = {
                            "name": ref["company_name"],
                            "industry": ref.get("industry"),
                        }
                        for s_org in page.get("schema_organizations", []):
                            if s_org.get("name") and ref["company_name"].lower() in s_org["name"].lower():
                                if s_org.get("url"):
                                    comp_data["website"] = s_org["url"]
                                if s_org.get("email"):
                                    comp_data["public_contact"] = {"email": s_org["email"]}

                        comp = await company_service.create(comp_data)
                        company_id = comp.get("id")
                        if comp.get("created", False):
                            companies_created += 1
                            await log_job_event(
                                db, job_id, "extracting", "success", "new_crm_record_saved",
                                f"Saved company CRM record: {ref['company_name']}"
                            )

                    # Contact creation
                    contact_id = None
                    target_contact_name = ref.get("person_name") or ref.get("company_name")
                    if target_contact_name:
                        prof_urls = {}
                        for soc in page.get("social_profiles", []):
                            plat = soc.get("platform", "").lower()
                            if soc.get("url") and plat in ("linkedin", "twitter", "instagram", "facebook", "youtube", "github"):
                                prof_urls[plat] = soc["url"]

                        page_emails = page.get("public_emails", [])
                        page_phones = page.get("public_phones", [])
                        source_url = page.get("url") or ref.get("source_url") or ""

                        initial_channels: List[Dict[str, Any]] = []
                        for plat, s_url in prof_urls.items():
                            initial_channels.append({
                                "type": "social",
                                "scope": "person_direct_work",
                                "value": s_url,
                                "source_url": source_url,
                                "source_type": "webpage",
                                "evidence_quote": f"Discovered {plat} profile link",
                                "syntax_valid": True,
                                "source_verified": True,
                                "verification_status": "published",
                                "confidence": 0.85,
                            })

                        contact_email = page_emails[0] if page_emails else None
                        contact_phone = page_phones[0] if page_phones else None

                        b_contacts = {}
                        if contact_email:
                            b_contacts["email"] = contact_email
                        if contact_phone:
                            b_contacts["phone"] = contact_phone

                        contact, was_new = await contact_service.create({
                            "full_name": target_contact_name,
                            "designation": ref.get("designation") or ("Client Account / Executive Office" if not ref.get("person_name") else "Executive"),
                            "company_id": company_id,
                            "company_name": ref.get("company_name"),
                            "contact_verification_status": "discovered",
                            "source_references": [ref_doc.get("id")],
                            "email": contact_email,
                            "phone": contact_phone,
                            "business_contacts": b_contacts,
                            "professional_urls": prof_urls,
                            "linkedin_url": prof_urls.get("linkedin"),
                            "contact_channels": initial_channels,
                        })
                        contact_id = contact.get("id")
                        if contact_id and contact_id not in all_job_contact_ids:
                            all_job_contact_ids.append(contact_id)
                        if was_new:
                            contacts_created += 1
                            await log_job_event(
                                db, job_id, "extracting", "success", "contact_found",
                                f"Discovered contact: {target_contact_name}"
                            )

                    # Lead creation
                    if contact_id:
                        lead_res = await lead_service.create(
                            contact_id=contact_id,
                            company_id=company_id,
                            lead_source=provider_id,
                            initial_stage="discovered",
                        )
                        if lead_res.get("created", False):
                            leads_created += 1
                            await log_job_event(
                                db, job_id, "extracting", "success", "new_crm_record_saved",
                                f"Generated new lead for {target_contact_name}"
                            )

                except Exception as e:
                    logger.exception("[CRM] error creating record")
                    warnings.append(_err("crm", str(e), url=ref.get("source_url"), err_type="crm"))

        # Check cancellation before contact enrichment
        if await self.is_job_cancelled(db, job_id):
            await self._handle_cancellation(db, job_id, "pre-enrichment")
            return

        # ---------- Stage 4b: Contact Enrichment ----------
        enrichment_metrics = {
            "total_contacts_enriched": 0,
            "direct_emails_found": 0,
            "direct_phones_found": 0,
            "generic_emails_found": 0,
            "company_phones_found": 0,
            "contact_forms_found": 0,
            "no_public_contacts_found": 0,
        }
        if all_job_contact_ids:
            await self._stage(db, job_id, "enriching_contacts", 78)
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

        data_quality_metrics = {
            "pages_processed": len([p for p in crawled_pages if p.get("status") == "success"]),
            "pages_analysed": pages_analysed,
            "candidates_detected": candidates_detected,
            "valid_client_references": valid_client_references,
            "company_only_references": company_only_references,
            "featured_personalities": featured_personalities,
            "collaborators": collaborators,
            "ordinary_mentions": ordinary_mentions,
            "rejected_false_matches": rejected_false_matches,
            "pending_verification": pending_verification,
            "contacts_created": contacts_created,
            "companies_created": companies_created,
            "leads_created": leads_created,
            "confidence_distribution": confidence_bands,
            "enrichment_metrics": enrichment_metrics,
        }

        # ---------- Stage 5: Report ----------
        await self._stage(db, job_id, "generating_report", 90)
        try:
            await self._generate_report(
                db, job_id, provider_id, start_url, crawled_pages,
                valid_client_references, data_quality_metrics, rejected_sample
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
            data_quality_metrics
        )
        await log_job_event(
            db, job_id, "completed", "success", "job_completed",
            f"Research complete: {valid_client_references} refs, {contacts_created} contacts, {leads_created} leads"
        )
        logger.info(
            "[JOB] %s done. refs=%d contacts=%d companies=%d leads=%d",
            job_id, valid_client_references, contacts_created, companies_created, leads_created,
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
                      refs, contacts, companies, leads, data_quality_metrics: Optional[Dict] = None):
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
            "lock_key": None,
            "locked_at": None,
            "completed_at": now,
            "updated_at": now,
        }
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
                               rejected_sample: Optional[List[Dict]] = None):
        success_pages = [p for p in pages if p.get("status") == "success"]
        failed_pages = [p for p in pages if p.get("status") == "failed"]

        socials: Dict[str, List[str]] = {}
        for p in success_pages:
            for sp in (p.get("social_profiles") or []):
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

        report = {
            "job_id": job_id,
            "provider_id": provider_id,
            "starting_url": start_url,
            "status": "completed",
            "pages_discovered": len(pages),
            "pages_processed": len(success_pages),
            "pages_failed": len(failed_pages),
            "references_found": references_found,
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
