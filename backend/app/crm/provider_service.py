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
    sort_by: str = "created_at",
    sort_dir: int = -1,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if search:
        query["$text"] = {"$search": search}
    if category:
        query["category"] = category
    if country:
        query["country"] = country
    if verification_status:
        query["verification_status"] = verification_status
    if discovery_status:
        query["discovery_status"] = discovery_status

    total = await db.providers.count_documents(query)
    cursor = db.providers.find(query).sort(sort_by, sort_dir).skip(skip).limit(limit)
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

