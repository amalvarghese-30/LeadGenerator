import logging
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.discovery.ddgs_search import DDGSSearch
from app.discovery.google_dorking import GoogleDorkingHelper
from app.schemas.discovery import SearchRequest
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discovery", tags=["Discovery"])


def _fmt_job(doc: dict) -> dict:
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    for f in ("created_at", "started_at", "completed_at", "updated_at", "locked_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
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

    job_doc = {
        "provider_id": provider_id,
        "starting_url": target_url,
        "job_type": "full_research",
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
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.crawl_jobs.insert_one(job_doc)
    job_doc["_id"] = result.inserted_id

    await db.providers.update_one(
        {"_id": ObjectId(provider_id)},
        {"$set": {"discovery_status": "researching",
                  "crawl_job_id": str(result.inserted_id)}},
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
    res = await db.crawl_jobs.update_one(
        {"_id": ObjectId(job_id), "status": {"$in": ["pending", "running"]}},
        {"$set": {"status": "cancelled", "completed_at": datetime.utcnow()}},
    )
    if res.modified_count == 0:
        raise HTTPException(400, "Job cannot be cancelled")
    return {"message": "Cancelled"}


@router.post("/jobs/{job_id}/retry")
async def retry_job_route(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    job = await db.crawl_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(404, "Job not found")
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
            "retry_count": job.get("retry_count", 0) + 1,
            "updated_at": datetime.utcnow(),
        }},
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