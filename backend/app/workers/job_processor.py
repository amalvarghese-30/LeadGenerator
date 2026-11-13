"""
Background Job Processor.
- Atomic job locking
- Explicit stage transitions
- Per-page persistence to crawl_pages
- Research report generation
- Honest error/warning reporting
"""
import asyncio
import os
import logging
from datetime import datetime, timedelta
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
        "timestamp": datetime.utcnow().isoformat(),
    }


class JobProcessor:
    def __init__(self):
        self.worker_id = f"worker-{os.getpid()}-{int(datetime.utcnow().timestamp())}"
        self.discovery_manager = DiscoveryManager()
        self.crawler_manager = CrawlerManager(max_pages=MAX_PAGES_PER_JOB)
        self.client_classifier = ClientClassifier()
        self.running = True

    # ------------------------------------------------------------------
    async def acquire_job(self, db) -> Optional[Dict[str, Any]]:
        lock_cutoff = datetime.utcnow() - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
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
                "locked_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        }
        job = await db.crawl_jobs.find_one_and_update(
            query, update, return_document=True,
        )
        return job

    # ------------------------------------------------------------------
    async def process_job(self, job: Dict[str, Any], db):
        job_id = str(job["_id"])
        provider_id = job.get("provider_id")
        start_url = job.get("starting_url") or job.get("target_url")

        logger.info("[JOB] Processing %s | provider=%s | url=%s", job_id, provider_id, start_url)

        if not start_url:
            await self._fail(db, job_id, _err("startup", "missing starting_url", err_type="config"))
            return

        errors: List[Dict] = []
        warnings: List[Dict] = []

        # ---------- Stage 1: URL discovery ----------
        try:
            await self._stage(db, job_id, "discovering", 5)
            discovery = await self.discovery_manager.discover_all_urls(start_url)
            discovered_urls = [
                d["url"] for d in discovery.get("discovered_urls", [])
                if isinstance(d, dict) and d.get("url")
            ][: MAX_PAGES_PER_JOB]

            # If discovery returned nothing, crawl the start_url directly
            if not discovered_urls:
                discovered_urls = [start_url]

            await db.crawl_jobs.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "pages_discovered": len(discovered_urls),
                    "discovery_stats": discovery.get("sources_breakdown", {}),
                    "progress_pct": 20,
                    "updated_at": datetime.utcnow(),
                }},
            )
            logger.info("[DISCOVERY] %d unique URLs found", len(discovered_urls))
        except Exception as e:
            logger.exception("[DISCOVERY] failed")
            errors.append(_err("discovery", e, err_type="discovery"))
            # Fall back to crawling just the start URL
            discovered_urls = [start_url]

        # ---------- Stage 2: Crawl ----------
        crawled_pages: List[Dict] = []
        try:
            await self._stage(db, job_id, "crawling", 25)
            crawled_pages = await self.crawler_manager.crawl_urls(
                discovered_urls, job_id=job_id, db=db,
            )
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

            logger.info(
                "[CRAWLER] %d success / %d failed / %d skipped",
                len(success), len(failed), len(skipped),
            )

            if not success:
                raise RuntimeError(
                    f"No pages crawled successfully. First error: "
                    f"{errors[0]['message'] if errors else 'unknown'}"
                )
        except Exception as e:
            logger.exception("[CRAWLER] fatal")
            errors.append(_err("crawling", e, err_type="crawl_fatal"))
            await self._finish(db, job_id, "failed", errors, warnings, 0, 0, 0, 0)
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
                    "crawled_at": datetime.utcnow(),
                }
                r = await db.crawl_pages.insert_one(doc)
                crawl_page_ids.append(str(r.inserted_id))
        except Exception as e:
            logger.exception("[PAGES] persist failed")
            warnings.append(_err("persist_pages", e, err_type="mongo"))

        # ---------- Stage 4: Extraction ----------
        await self._stage(db, job_id, "extracting", 60)
        reference_service = ReferenceService(db)
        contact_service = ContactService(db)
        company_service = CompanyService(db)
        lead_service = LeadService(db)

        # Detailed Data-Quality Metrics (Task 10)
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

        for page in crawled_pages:
            if page.get("status") != "success":
                continue
            pages_analysed += 1
            try:
                refs, rejected, page_meta = await self.client_classifier.process_page_detailed(page, provider_id)
            except Exception as e:
                logger.exception("[EXTRACTION] error for %s", page.get("url"))
                warnings.append(_err("extraction", e, url=page.get("url"), err_type="extract"))
                continue

            candidates_detected += len(refs) + len(rejected)
            rejected_false_matches += len(rejected)
            for r in rejected:
                if len(rejected_sample) < 50:
                    rejected_sample.append({
                        "candidate_name": r.get("person_name") or r.get("company_name") or "unknown",
                        "rejection_reasons": r.get("rejection_reasons", []),
                        "source_url": r.get("source_url"),
                        "evidence_quote": (r.get("evidence_quote") or "")[:200],
                    })

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

                    # Save reference (idempotent by source_url + person_name/company_name)
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
                        continue

                    ref_doc = await reference_service.create(ref)
                    valid_client_references += 1
                    pending_verification += 1

                    # Company
                    company_id = None
                    if ref.get("company_name"):
                        comp = await company_service.create({
                            "name": ref["company_name"],
                            "industry": ref.get("industry"),
                        })
                        company_id = comp.get("id")
                        if comp.get("created", False):
                            companies_created += 1

                    # Contact (only created if a valid person name was extracted!)
                    contact_id = None
                    if ref.get("person_name"):
                        contact, was_new = await contact_service.create({
                            "full_name": ref["person_name"],
                            "designation": ref.get("designation"),
                            "company_id": company_id,
                            "company_name": ref.get("company_name"),
                            "contact_verification_status": "discovered",
                            "source_references": [ref_doc.get("id")],
                        })
                        contact_id = contact.get("id")
                        if was_new:
                            contacts_created += 1

                    # Lead (idempotent lead creation)
                    if contact_id:
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
                    warnings.append(_err(
                        "crm", e, url=ref.get("source_url"), err_type="crm",
                    ))

        # Data-quality summary dictionary
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
        }

        # ---------- Stage 5: Report ----------
        await self._stage(db, job_id, "generating_report", 90)
        try:
            await self._generate_report(
                db, job_id, provider_id, start_url, crawled_pages,
                valid_client_references, data_quality_metrics, rejected_sample
            )
        except Exception as e:
            logger.exception("[REPORT] failed")
            warnings.append(_err("report", e, err_type="report"))

        # ---------- Final ----------
        final_status = "completed" if not warnings and not errors else "completed_with_warnings"
        await self._finish(
            db, job_id, final_status, errors, warnings,
            valid_client_references, contacts_created, companies_created, leads_created,
            data_quality_metrics
        )
        logger.info(
            "[JOB] %s done. refs=%d contacts=%d companies=%d leads=%d",
            job_id, references_found, contacts_created, companies_created, leads_created,
        )

    # ------------------------------------------------------------------
    async def _stage(self, db, job_id: str, stage: str, progress: int):
        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "current_stage": stage,
                "progress_pct": progress,
                "updated_at": datetime.utcnow(),
            }},
        )

    async def _finish(self, db, job_id, status, errors, warnings,
                      refs, contacts, companies, leads, data_quality_metrics: Optional[Dict] = None):
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
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        if data_quality_metrics:
            update_doc["data_quality_metrics"] = data_quality_metrics

        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_doc},
        )

    async def _fail(self, db, job_id, error: Dict):
        await db.crawl_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "status": "failed",
                "current_stage": "failed",
                "errors": [error],
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }},
        )

    async def _generate_report(self, db, job_id, provider_id, start_url,
                               pages: List[Dict], references_found: int,
                               data_quality_metrics: Optional[Dict] = None,
                               rejected_sample: Optional[List[Dict]] = None):
        success_pages = [p for p in pages if p.get("status") == "success"]
        failed_pages = [p for p in pages if p.get("status") == "failed"]

        # Social profiles across all pages
        socials: Dict[str, List[str]] = {}
        for p in success_pages:
            for sp in (p.get("social_profiles") or []):
                platform = sp.get("platform")
                url = sp.get("url")
                if platform and url:
                    socials.setdefault(platform, [])
                    if url not in socials[platform]:
                        socials[platform].append(url)

        # Emails across all pages
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
            "rejected_candidates": rejected_sample or [],
            "social_media_profiles": socials,
            "public_emails_discovered": sorted(emails),
            "failed_urls": [
                {"url": p.get("url"), "error": p.get("error")}
                for p in failed_pages
            ],
            "generated_at": datetime.utcnow(),
        }
        await db.research_reports.replace_one(
            {"job_id": job_id}, report, upsert=True,
        )

    # ------------------------------------------------------------------
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
                                         _err("worker", e, err_type="worker_fatal"))
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