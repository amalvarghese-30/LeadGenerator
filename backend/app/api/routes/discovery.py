import asyncio
import json
import logging
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
    page_limit: Optional[int] = Query(None, ge=1, le=100),
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

    now = datetime.now(timezone.utc)
    job_doc = {
        "provider_id": provider_id,
        "starting_url": target_url,
        "job_type": "full_research",
        "max_pages": page_limit or 30,
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
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Retrieve historical persistent events for a research job."""
    docs = await db.job_events.find({"job_id": job_id}).sort("event_timestamp", 1).to_list(500)
    return [_fmt_event(d) for d in docs]


@router.get("/jobs/{job_id}/events/stream")
async def stream_job_events(
    job_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Server-Sent Events (SSE) live activity stream for a research job.
    """
    queue = await stream_manager.subscribe(job_id)

    async def event_generator():
        try:
            # Check if job is already in terminal state
            job_doc = None
            if ObjectId.is_valid(job_id):
                job_doc = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})

            # First send past events
            past = await db.job_events.find({"job_id": job_id}).sort("event_timestamp", 1).to_list(200)
            has_terminal = False
            for ev in past:
                formatted = _fmt_event(ev)
                yield f"data: {json.dumps(formatted)}\n\n"
                if formatted.get("event_type") in ("job_completed", "job_failed", "job_cancelled"):
                    has_terminal = True

            # If already terminated, send close event and finish stream cleanly
            if has_terminal or (job_doc and job_doc.get("status") in ("completed", "completed_with_warnings", "failed", "cancelled")):
                yield f"event: close\ndata: {json.dumps({'status': 'closed', 'message': 'Job execution finished'})}\n\n"
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("event_type") in ("job_completed", "job_failed", "job_cancelled"):
                        yield f"event: close\ndata: {json.dumps({'status': 'closed', 'event_type': event.get('event_type')})}\n\n"
                        break
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await stream_manager.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
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
