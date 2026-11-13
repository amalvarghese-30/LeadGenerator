from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.deduplication import generate_company_dedup_key
from app.utils.url_utils import extract_domain


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_company(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Dict:
    now = datetime.now(timezone.utc)
    domain = data.get("domain") or extract_domain(data.get("website", ""))
    dedup_key = generate_company_dedup_key(
        name=data["name"],
        domain=domain,
        linkedin_url=data.get("linkedin_url"),
    )
    # Check for existing
    existing = await db.companies.find_one({"dedup_key": dedup_key})
    if existing:
        return _doc_to_dict(existing)

    doc = {
        **data,
        "domain": domain,
        "dedup_key": dedup_key,
        "verification_status": "unverified",
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.companies.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc)


async def get_company(db: AsyncIOMotorDatabase, company_id: str) -> Optional[Dict]:
    try:
        doc = await db.companies.find_one({"_id": ObjectId(company_id)})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


async def list_companies(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if search:
        query["$text"] = {"$search": search}
    if industry:
        query["industry"] = industry
    if country:
        query["country"] = country

    total = await db.companies.count_documents(query)
    cursor = db.companies.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def update_company(db: AsyncIOMotorDatabase, company_id: str, data: Dict) -> Optional[Dict]:
    data["updated_at"] = datetime.now(timezone.utc)
    try:
        result = await db.companies.find_one_and_update(
            {"_id": ObjectId(company_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result) if result else None
    except Exception:
        return None


async def delete_company(db: AsyncIOMotorDatabase, company_id: str) -> bool:
    try:
        result = await db.companies.delete_one({"_id": ObjectId(company_id)})
        return result.deleted_count > 0
    except Exception:
        return False


class CompanyService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict, user_id: Optional[str] = None) -> Dict:
        doc = await create_company(self.db, data, user_id)
        # Mark whether this was a new creation for the worker counter
        if doc and not doc.get("id"):
            doc["_existing"] = True
        return doc

    async def get_by_id(self, company_id: str) -> Optional[Dict]:
        return await get_company(self.db, company_id)

    async def list(self, skip: int = 0, limit: int = 20, search: Optional[str] = None,
                   industry: Optional[str] = None, country: Optional[str] = None):
        return await list_companies(self.db, skip, limit, search, industry, country)

    async def update(self, company_id: str, data: Dict) -> Optional[Dict]:
        return await update_company(self.db, company_id, data)

    async def delete(self, company_id: str) -> bool:
        return await delete_company(self.db, company_id)