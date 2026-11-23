from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.url_utils import extract_domain


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_provider(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Dict:
    now = datetime.now(timezone.utc)
    if not data.get("domain") and data.get("website"):
        data["domain"] = extract_domain(data["website"])
    
    if data.get("domain"):
        existing = await db.providers.find_one({"domain": data["domain"]})
        if existing:
            return _doc_to_dict(existing)

    doc = {
        **data,
        "discovery_status": "discovered",
        "verification_status": "unverified",
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.providers.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc)


async def get_provider(db: AsyncIOMotorDatabase, provider_id: str) -> Optional[Dict]:
    try:
        doc = await db.providers.find_one({"_id": ObjectId(provider_id)})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


async def list_providers(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    verification_status: Optional[str] = None,
    discovery_status: Optional[str] = None,
    scanned_only: Optional[bool] = None,
    scan_status: Optional[str] = "all",
    sort_by: str = "last_crawled_at",
    sort_dir: int = -1,
) -> Tuple[List[Dict], int]:
    match_stage: Dict[str, Any] = {}
    if search:
        match_stage["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"domain": {"$regex": search, "$options": "i"}},
            {"website": {"$regex": search, "$options": "i"}},
        ]
    if category:
        match_stage["category"] = category
    if country:
        match_stage["country"] = country
    if verification_status:
        match_stage["verification_status"] = verification_status
    if discovery_status:
        match_stage["discovery_status"] = discovery_status

    pipeline: List[Dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    # Join crawl_jobs
    pipeline.extend([
        {
            "$lookup": {
                "from": "crawl_jobs",
                "let": {"pid": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$provider_id", "$$pid"]}}},
                    {"$sort": {"created_at": -1}},
                ],
                "as": "scan_jobs",
            }
        },
        {
            "$addFields": {
                "total_scans_count": {"$size": "$scan_jobs"},
                "latest_job": {"$arrayElemAt": ["$scan_jobs", 0]},
                "last_crawled_at": {
                    "$ifNull": [
                        {"$max": "$scan_jobs.created_at"},
                        "$last_crawled_at",
                    ]
                },
                "pages_crawled": {"$ifNull": [{"$sum": "$scan_jobs.pages_crawled"}, 0]},
                "references_found": {"$ifNull": [{"$sum": "$scan_jobs.references_found"}, 0]},
                "companies_found": {"$ifNull": [{"$sum": "$scan_jobs.companies_created"}, 0]},
                "contacts_found": {"$ifNull": [{"$sum": "$scan_jobs.contacts_created"}, 0]},
                "leads_found": {"$ifNull": [{"$sum": "$scan_jobs.leads_created"}, 0]},
            }
        },
        {
            "$addFields": {
                "latest_job_id": {
                    "$cond": [{"$ifNull": ["$latest_job._id", False]}, {"$toString": "$latest_job._id"}, None]
                },
                "latest_job_status": "$latest_job.status",
                "latest_job_progress_pct": "$latest_job.progress_pct",
            }
        },
    ])

    # Apply scanned_only and scan_status filters
    post_match: Dict[str, Any] = {}
    if scanned_only or scan_status == "scanned":
        post_match["$or"] = [{"total_scans_count": {"$gt": 0}}, {"last_crawled_at": {"$ne": None}}]
    elif scan_status == "researching":
        post_match["latest_job_status"] = "running"
    elif scan_status == "completed":
        post_match["latest_job_status"] = {"$in": ["completed", "completed_with_warnings"]}
    elif scan_status == "failed":
        post_match["latest_job_status"] = "failed"
    elif scan_status == "never_scanned":
        post_match["total_scans_count"] = 0

    if post_match:
        pipeline.append({"$match": post_match})

    # Count facet and data facet
    pipeline.append({
        "$facet": {
            "metadata": [{"$count": "total"}],
            "data": [
                {"$sort": {sort_by: sort_dir, "created_at": -1}},
                {"$skip": skip},
                {"$limit": limit},
                {"$project": {"scan_jobs": 0, "latest_job": 0}},
            ],
        }
    })

    result = await db.providers.aggregate(pipeline).to_list(length=1)
    if not result:
        return [], 0

    facet_result = result[0]
    total_docs = facet_result.get("metadata", [])
    total = total_docs[0]["total"] if total_docs else 0
    items = [_doc_to_dict(d) for d in facet_result.get("data", [])]
    return items, total


async def list_provider_scans(
    db: AsyncIOMotorDatabase,
    provider_id: str,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict], int]:
    try:
        oid = ObjectId(provider_id)
        query = {"$or": [{"provider_id": oid}, {"provider_id": provider_id}]}
    except Exception:
        query = {"provider_id": provider_id}

    total = await db.crawl_jobs.count_documents(query)
    cursor = db.crawl_jobs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def update_provider(db: AsyncIOMotorDatabase, provider_id: str, data: Dict) -> Optional[Dict]:
    data["updated_at"] = datetime.now(timezone.utc)
    try:
        result = await db.providers.find_one_and_update(
            {"_id": ObjectId(provider_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result) if result else None
    except Exception:
        return None


async def delete_provider(db: AsyncIOMotorDatabase, provider_id: str) -> bool:
    try:
        result = await db.providers.delete_one({"_id": ObjectId(provider_id)})
        return result.deleted_count > 0
    except Exception:
        return False


async def mark_provider_crawled(db: AsyncIOMotorDatabase, provider_id: str, error: Optional[str] = None) -> None:
    update: Dict[str, Any] = {
        "last_crawled_at": datetime.now(timezone.utc),
        "discovery_status": "error" if error else "crawled",
        "updated_at": datetime.now(timezone.utc),
    }
    if error:
        update["crawl_error"] = error
    try:
        await db.providers.update_one({"_id": ObjectId(provider_id)}, {"$set": update})
    except Exception:
        pass


class ProviderService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict, user_id: Optional[str] = None) -> Dict:
        return await create_provider(self.db, data, user_id)

    async def get_by_id(self, provider_id: str) -> Optional[Dict]:
        return await get_provider(self.db, provider_id)

    async def list(self, skip: int = 0, limit: int = 20, search: Optional[str] = None, category: Optional[str] = None, country: Optional[str] = None, verification_status: Optional[str] = None) -> Tuple[List[Dict], int]:
        return await list_providers(self.db, skip, limit, search, category, country, verification_status)

    async def update(self, provider_id: str, data: Dict) -> Optional[Dict]:
        return await update_provider(self.db, provider_id, data)

    async def delete(self, provider_id: str) -> bool:
        return await delete_provider(self.db, provider_id)

