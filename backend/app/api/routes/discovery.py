import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.discovery.ddgs_search import DDGSSearch
from app.discovery.google_dorking import GoogleDorkingHelper
from app.schemas.discovery import SearchRequest
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit
from app.utils.job_logger import log_job_event, stream_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discovery", tags=["Discovery"])


def _fmt_job(doc: dict) -> dict:
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    for f in ("created_at", "started_at", "completed_at", "updated_at", "locked_at", "cancelled_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc


def _fmt_event(doc: dict) -> dict:
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    if doc.get("event_timestamp") and hasattr(doc["event_timestamp"], "isoformat"):
        doc["event_timestamp"] = doc["event_timestamp"].isoformat()
    return doc


@router.post("/providers")
async def search_providers_route(
    data: SearchRequest,
    _user: dict = Depends(get_current_user),
):
    searcher = DDGSSearch(max_results=data.max_results)
    results = searcher.search(data.query, region=data.country_filter or "wt-wt")
    return {"query": data.query, "count": len(results), "results": results}


@router.post("/providers/{provider_id}/research")
async def research_provider_route(
    provider_id: str,
    page_limit: Optional[int] = Query(None, ge=1, le=500),
    job_type: Optional[str] = Query("full_research"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    provider = await db.providers.find_one({"_id": ObjectId(provider_id)})
    if not provider:
        raise HTTPException(404, "Provider not found")

    target_url = provider.get("website")
    if not target_url:
        raise HTTPException(400, "Provider has no website URL")

    active = await db.crawl_jobs.find_one({
        "provider_id": provider_id,
        "status": {"$in": ["pending", "running"]},
    })
    if active:
        return _fmt_job(active)

    eff_job_type = job_type or "full_research"
    if eff_job_type == "full_research" and target_url:
        path_l = target_url.lower()
        if any(seg in path_l for seg in ["/wiki/", "/person/", "/profile/", "/people/", "/author/", "/leadership/", "/executive/"]):
            eff_job_type = "person_profile"

    safety_max = getattr(settings, "CRAWLER_SAFETY_MAX_PAGES", 500)
    default_max = getattr(settings, "CRAWLER_MAX_PAGES_PER_JOB", 50)
    if page_limit is not None:
        if page_limit < 1:
            raise HTTPException(400, "page_limit must be at least 1")
        if page_limit > safety_max:
            raise HTTPException(400, f"page_limit cannot exceed safety limit of {safety_max}")
        eff_max_pages = page_limit
    else:
        eff_max_pages = default_max

    now = datetime.now(timezone.utc)
    job_doc = {
        "provider_id": provider_id,
        "starting_url": target_url,
        "job_type": eff_job_type,
        "max_pages": eff_max_pages,
        "status": "pending",
        "current_stage": "queued",
        "progress_pct": 0,
        "pages_discovered": 0,
        "pages_attempted": 0,
        "pages_crawled": 0,
        "pages_failed": 0,
        "pages_skipped": 0,
        "pages_analysed": 0,
        "references_found": 0,
        "contacts_created": 0,
        "companies_created": 0,
        "leads_created": 0,
        "errors": [],
        "warnings": [],
        "created_by": str(user.get("_id", "")),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.crawl_jobs.insert_one(job_doc)
    job_doc["_id"] = result.inserted_id

    await db.providers.update_one(
        {"_id": ObjectId(provider_id)},
        {"$set": {"discovery_status": "researching",
                  "crawl_job_id": str(result.inserted_id)}},
    )

    await log_job_event(
        db, str(result.inserted_id), "queued", "info", "job_created",
        f"Research job queued for provider {provider.get('name', 'Unknown')}"
    )

    return _fmt_job(job_doc)


@router.get("/jobs", response_model=PaginatedResponse)
async def list_jobs_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    q: Dict[str, Any] = {}
    if provider_id:
        q["provider_id"] = provider_id
    if status_filter:
        q["status"] = status_filter
    total = await db.crawl_jobs.count_documents(q)
    docs = await db.crawl_jobs.find(q).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return paginate([_fmt_job(d) for d in docs], total, page, limit)


@router.get("/jobs/{job_id}")
async def get_job_route(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        doc = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(404, "Job not found")
    if not doc:
        raise HTTPException(404, "Job not found")
    return _fmt_job(doc)


@router.get("/jobs/{job_id}/events")
async def get_job_events_route(
    job_id: str,
    since_id: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Retrieve historical persistent events for a research job with cursor support."""
    query: Dict[str, Any] = {"job_id": job_id}
    if since_id and ObjectId.is_valid(since_id):
        query["_id"] = {"$gt": ObjectId(since_id)}
    docs = await db.job_events.find(query).sort("_id", 1).to_list(limit)
    return [_fmt_event(d) for d in docs]


@router.get("/jobs/{job_id}/events/stream")
async def stream_job_events(
    job_id: str,
    request: Request,
    since_id: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Server-Sent Events (SSE) live activity stream for a research job.
    Supports cross-process MongoDB event delivery, cursor resuming, and keepalives.
    """
    queue = await stream_manager.subscribe(job_id)

    header_last_id = request.headers.get("Last-Event-ID")
    start_cursor = since_id or header_last_id

    async def event_generator():
        latest_seen_id = start_cursor if (start_cursor and ObjectId.is_valid(start_cursor)) else None
        try:
            # Check if job document exists and current status
            job_doc = None
            if ObjectId.is_valid(job_id):
                job_doc = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})

            # 1. Yield all historical/unread events from MongoDB
            initial_query: Dict[str, Any] = {"job_id": job_id}
            if latest_seen_id and ObjectId.is_valid(latest_seen_id):
                initial_query["_id"] = {"$gt": ObjectId(latest_seen_id)}

            cursor = db.job_events.find(initial_query).sort("_id", 1)
            has_terminal = False
            async for doc in cursor:
                latest_seen_id = str(doc["_id"])
                ev = _fmt_event(doc)
                event_type = ev.get("event_type", "message")
                yield f"id: {latest_seen_id}\nevent: {event_type}\ndata: {json.dumps(ev)}\n\n"
                if event_type in ("job_completed", "job_failed", "job_cancelled"):
                    has_terminal = True

            # If already terminated in DB or events, close cleanly
            is_terminal_status = bool(job_doc and job_doc.get("status") in ("completed", "completed_with_warnings", "failed", "cancelled"))
            if has_terminal or is_terminal_status:
                yield f"event: close\ndata: {json.dumps({'status': 'closed', 'message': 'Job execution finished'})}\n\n"
                return

            # 2. Live streaming loop (hybrid: polling MongoDB + in-memory queue)
            last_heartbeat = asyncio.get_event_loop().time()
            while True:
                if await request.is_disconnected():
                    break

                # Check MongoDB for newly inserted events from external workers
                poll_query: Dict[str, Any] = {"job_id": job_id}
                if latest_seen_id and ObjectId.is_valid(latest_seen_id):
                    poll_query["_id"] = {"$gt": ObjectId(latest_seen_id)}

                new_docs = await db.job_events.find(poll_query).sort("_id", 1).to_list(100)
                for doc in new_docs:
                    latest_seen_id = str(doc["_id"])
                    ev = _fmt_event(doc)
                    event_type = ev.get("event_type", "message")
                    yield f"id: {latest_seen_id}\nevent: {event_type}\ndata: {json.dumps(ev)}\n\n"
                    if event_type in ("job_completed", "job_failed", "job_cancelled"):
                        yield f"event: close\ndata: {json.dumps({'status': 'closed', 'event_type': event_type})}\n\n"
                        return

                # Check if job reached a terminal status in MongoDB
                current_job = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)}, {"status": 1}) if ObjectId.is_valid(job_id) else None
                if current_job and current_job.get("status") in ("completed", "completed_with_warnings", "failed", "cancelled"):
                    tail_docs = await db.job_events.find(poll_query).sort("_id", 1).to_list(50)
                    for doc in tail_docs:
                        latest_seen_id = str(doc["_id"])
                        ev = _fmt_event(doc)
                        event_type = ev.get("event_type", "message")
                        yield f"id: {latest_seen_id}\nevent: {event_type}\ndata: {json.dumps(ev)}\n\n"
                    yield f"event: close\ndata: {json.dumps({'status': 'closed', 'job_status': current_job.get('status')})}\n\n"
                    return

                # Await in-memory queue with 1.5s timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.5)
                    ev_id = event.get("id") or str(event.get("_id", ""))
                    if not ev_id or (latest_seen_id and ev_id > latest_seen_id) or not latest_seen_id:
                        if ev_id:
                            latest_seen_id = ev_id
                        event_type = event.get("event_type", "message")
                        yield f"id: {latest_seen_id}\nevent: {event_type}\ndata: {json.dumps(event)}\n\n"
                        if event_type in ("job_completed", "job_failed", "job_cancelled"):
                            yield f"event: close\ndata: {json.dumps({'status': 'closed', 'event_type': event_type})}\n\n"
                            return
                except asyncio.TimeoutError:
                    now_time = asyncio.get_event_loop().time()
                    if now_time - last_heartbeat >= 10.0:
                        last_heartbeat = now_time
                        yield ": ping\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await stream_manager.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{job_id}/report")
async def get_job_report(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    report = await db.research_reports.find_one({"job_id": job_id})
    if not report:
        raise HTTPException(404, "Report not ready yet")
    if "_id" in report:
        report["id"] = str(report.pop("_id"))
    if report.get("generated_at") and hasattr(report["generated_at"], "isoformat"):
        report["generated_at"] = report["generated_at"].isoformat()
    return report


@router.get("/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(400, "Invalid job ID")
    job = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(404, "Job not found")

    provider_id = job.get("provider_id")
    match_conditions = []
    if job_id:
        match_conditions.append({"job_id": job_id})
    if provider_id:
        match_conditions.append({"provider_id": str(provider_id)})
        if ObjectId.is_valid(str(provider_id)):
            match_conditions.append({"provider_id": ObjectId(str(provider_id))})

    query = {"$or": match_conditions} if match_conditions else {}
    refs_cursor = db.provider_client_references.find(query).sort("confidence", -1).limit(100)
    references = await refs_cursor.to_list(100)

    results = []
    for ref in references:
        ref_id = str(ref["_id"])
        comp_name = ref.get("company_name") or ref.get("client_name")
        person_name = ref.get("person_name")
        company_id = ref.get("company_id")

        company = None
        if company_id and ObjectId.is_valid(company_id):
            company = await db.companies.find_one({"_id": ObjectId(company_id)})
        if not company and comp_name:
            company = await db.companies.find_one({"name": {"$regex": f"^{re.escape(comp_name)}$", "$options": "i"}})

        contact = None
        if ref_id:
            contact = await db.contacts.find_one({"source_references": ref_id})
        if not contact and person_name:
            contact = await db.contacts.find_one({"full_name": {"$regex": f"^{re.escape(person_name)}$", "$options": "i"}})

        comp_pub_contact = company.get("public_contact") or {} if company else {}
        comp_channels = company.get("public_contact_channels") or [] if company else []
        comp_socials = company.get("social_profiles") or [] if company else []

        # Find best email and phone across contact and company
        best_email = (
            contact.get("email")
            if contact and contact.get("email")
            else (comp_pub_contact.get("email") or next((c["value"] for c in comp_channels if c.get("type") == "email"), None))
        )
        best_phone = (
            contact.get("phone")
            if contact and contact.get("phone")
            else (comp_pub_contact.get("phone") or next((c["value"] for c in comp_channels if c.get("type") == "phone"), None))
        )
        best_linkedin = (
            contact.get("linkedin_url")
            if contact and contact.get("linkedin_url")
            else (company.get("linkedin_url") if company else None)
        )

        all_channels = list(comp_channels)
        if contact and contact.get("contact_channels"):
            existing_c_vals = {c.get("value") for c in all_channels if isinstance(c, dict)}
            for cc in contact["contact_channels"]:
                if isinstance(cc, dict) and cc.get("value") not in existing_c_vals:
                    all_channels.append(cc)

        # Collect emails list
        emails_list = []
        if company and company.get("emails"):
            emails_list.extend(company["emails"])
        elif comp_pub_contact.get("emails"):
            emails_list.extend(comp_pub_contact["emails"])
        for c in all_channels:
            if isinstance(c, dict) and c.get("type") == "email" and c.get("value"):
                emails_list.append(c["value"])
        if best_email and best_email not in emails_list:
            emails_list.insert(0, best_email)
        emails_list = list(dict.fromkeys(emails_list))

        # Collect phones list
        phones_list = []
        if company and company.get("phones"):
            phones_list.extend(company["phones"])
        elif comp_pub_contact.get("phones"):
            phones_list.extend(comp_pub_contact["phones"])
        for c in all_channels:
            if isinstance(c, dict) and c.get("type") == "phone" and c.get("value"):
                phones_list.append(c["value"])
        if best_phone and best_phone not in phones_list:
            phones_list.insert(0, best_phone)
        phones_list = list(dict.fromkeys(phones_list))

        # Collect socials dict
        socials_dict = {
            "linkedin": None,
            "instagram": None,
            "facebook": None,
            "twitter": None,
            "youtube": None,
        }
        if company and isinstance(company.get("socials"), dict):
            for k in socials_dict.keys():
                if company["socials"].get(k):
                    socials_dict[k] = company["socials"][k]
        elif comp_pub_contact.get("socials") and isinstance(comp_pub_contact["socials"], dict):
            for k in socials_dict.keys():
                if comp_pub_contact["socials"].get(k):
                    socials_dict[k] = comp_pub_contact["socials"][k]

        if best_linkedin and not socials_dict["linkedin"]:
            socials_dict["linkedin"] = best_linkedin

        for sp in comp_socials:
            if isinstance(sp, dict):
                plat = (sp.get("platform") or "").lower()
                if plat in socials_dict and not socials_dict[plat] and sp.get("url"):
                    socials_dict[plat] = sp["url"]
        for c in all_channels:
            if isinstance(c, dict) and c.get("type") == "social" and c.get("value"):
                s_val = c["value"].lower()
                for plat in socials_dict.keys():
                    if plat in s_val and not socials_dict[plat]:
                        socials_dict[plat] = c["value"]

        website_val = (
            (company.get("website") if company else None)
            or ref.get("company_website")
            or ref.get("client_website")
            or ref.get("verified_website")
            or ref.get("client_url")
            or ref.get("website")
        )

        results.append({
            "id": ref_id,
            "company_id": str(company["_id"]) if company else company_id,
            "company_name": comp_name or (company.get("name") if company else None),
            "company_website": website_val,
            "website": website_val,
            "emails": emails_list,
            "phones": phones_list,
            "socials": socials_dict,
            "industry": ref.get("industry") or (company.get("industry") if company else None),
            "person_name": person_name or (contact.get("full_name") if contact else None),
            "designation": ref.get("designation") or (contact.get("designation") if contact else None),
            "relationship_type": ref.get("relationship_type") or ref.get("reference_type", "client_portfolio_reference"),
            "confidence": float(ref.get("confidence") or ref.get("confidence_score") or 0.8),
            "evidence_quote": ref.get("evidence_quote") or ref.get("evidence_snippet"),
            "source_url": ref.get("source_url") or ref.get("evidence_url"),
            "verification_status": ref.get("verification_status", "pending_review"),
            "enrichment_status": company.get("enrichment_status", "pending") if company else "pending",
            "contacts": {
                "email": best_email,
                "emails": emails_list,
                "phone": best_phone,
                "phones": phones_list,
                "socials": socials_dict,
                "linkedin": best_linkedin,
                "channels": all_channels,
                "social_profiles": comp_socials,
            }
        })

    return {
        "job_id": job_id,
        "status": job.get("status"),
        "total_results": len(results),
        "results": results
    }


@router.get("/jobs/{job_id}/companies")
async def get_job_companies(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(400, "Invalid job ID")
    job = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(404, "Job not found")

    provider_id = job.get("provider_id")
    refs = await db.provider_client_references.find({"provider_id": provider_id}).to_list(100)
    comp_ids = [ObjectId(r["company_id"]) for r in refs if r.get("company_id") and ObjectId.is_valid(r["company_id"])]
    companies = []
    if comp_ids:
        docs = await db.companies.find({"_id": {"$in": comp_ids}}).to_list(100)
        for d in docs:
            d["id"] = str(d.pop("_id"))
            for dt in ("created_at", "updated_at", "last_enriched_at"):
                if d.get(dt) and hasattr(d[dt], "isoformat"):
                    d[dt] = d[dt].isoformat()
            companies.append(d)
    return {"job_id": job_id, "total": len(companies), "companies": companies}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_route(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Cancel a pending or running research job.
    Releases locks, records cancellation timestamp and reason, and logs cancellation event.
    """
    now = datetime.now(timezone.utc)
    res = await db.crawl_jobs.update_one(
        {"_id": ObjectId(job_id), "status": {"$in": ["pending", "running"]}},
        {"$set": {
            "status": "cancelled",
            "current_stage": "cancelled",
            "completed_at": now,
            "cancelled_at": now,
            "cancellation_reason": "user_cancelled",
            "lock_key": None,
            "locked_at": None,
            "updated_at": now,
        }},
    )
    if res.modified_count == 0:
        raise HTTPException(400, "Job is not in a cancellable state")

    await log_job_event(
        db, job_id, "cancelled", "warning", "job_cancelled",
        "Job was cancelled by user request",
        metadata={"cancelled_at": now.isoformat(), "cancellation_reason": "user_cancelled"}
    )

    return {"message": "Job successfully marked for cancellation", "job_id": job_id}


@router.post("/jobs/{job_id}/retry")
async def retry_job_route(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(404, "Job not found")

    now = datetime.now(timezone.utc)
    res = await db.crawl_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": "pending",
            "current_stage": "queued",
            "progress_pct": 0,
            "pages_discovered": 0,
            "pages_attempted": 0,
            "pages_crawled": 0,
            "pages_failed": 0,
            "pages_skipped": 0,
            "references_found": 0,
            "contacts_created": 0,
            "companies_created": 0,
            "leads_created": 0,
            "errors": [],
            "warnings": [],
            "lock_key": None,
            "locked_at": None,
            "started_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "cancellation_reason": None,
            "retry_count": job.get("retry_count", 0) + 1,
            "updated_at": now,
        }},
    )
    await log_job_event(
        db, job_id, "queued", "info", "job_retried",
        f"Job re-queued for retry (retry_count={job.get('retry_count', 0) + 1})"
    )
    return {"message": "Job re-queued", "modified": res.modified_count}


@router.get("/dorking")
async def get_dorking_queries(
    domain: str,
    brand_name: Optional[str] = None,
    _user: dict = Depends(get_current_user),
):
    helper = GoogleDorkingHelper()
    return {"domain": domain, "queries": helper.generate_queries(domain, brand_name or "")}
