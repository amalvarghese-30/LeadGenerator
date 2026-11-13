from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_activity(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Dict:
    now = datetime.now(timezone.utc)
    doc = {
        **data,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.activities.insert_one(doc)
    doc["_id"] = result.inserted_id
    # Update last_activity on lead
    if data.get("lead_id"):
        await db.leads.update_one(
            {"_id": ObjectId(data["lead_id"])},
            {"$set": {"last_activity": now, "updated_at": now}},
        )
    return _doc_to_dict(doc)


async def get_activity(db: AsyncIOMotorDatabase, activity_id: str) -> Optional[Dict]:
    try:
        doc = await db.activities.find_one({"_id": ObjectId(activity_id)})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


async def list_activities(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 50,
    lead_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    company_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    activity_type: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if lead_id:
        query["lead_id"] = lead_id
    if contact_id:
        query["contact_id"] = contact_id
    if company_id:
        query["company_id"] = company_id
    if provider_id:
        query["provider_id"] = provider_id
    if activity_type:
        query["activity_type"] = activity_type

    total = await db.activities.count_documents(query)
    cursor = db.activities.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def update_activity(db: AsyncIOMotorDatabase, activity_id: str, data: Dict) -> Optional[Dict]:
    data["updated_at"] = datetime.now(timezone.utc)
    try:
        result = await db.activities.find_one_and_update(
            {"_id": ObjectId(activity_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result) if result else None
    except Exception:
        return None


class ActivityService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict, user_id: Optional[str] = None) -> Dict:
        return await create_activity(self.db, data, user_id)

    async def get_by_id(self, activity_id: str) -> Optional[Dict]:
        return await get_activity(self.db, activity_id)

    async def list(self, skip: int = 0, limit: int = 50, lead_id: Optional[str] = None, contact_id: Optional[str] = None, company_id: Optional[str] = None, provider_id: Optional[str] = None, activity_type: Optional[str] = None) -> Tuple[List[Dict], int]:
        return await list_activities(self.db, skip, limit, lead_id, contact_id, company_id, provider_id, activity_type)

    async def update(self, activity_id: str, data: Dict) -> Optional[Dict]:
        return await update_activity(self.db, activity_id, data)

