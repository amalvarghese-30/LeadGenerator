from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_task(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Dict:
    now = datetime.now(timezone.utc)
    doc = {
        **data,
        "status": "open",  # open|in_progress|completed|cancelled
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.tasks.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc)


async def get_task(db: AsyncIOMotorDatabase, task_id: str) -> Optional[Dict]:
    try:
        doc = await db.tasks.find_one({"_id": ObjectId(task_id)})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


async def list_tasks(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    priority: Optional[str] = None,
    overdue_only: bool = False,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if assigned_to:
        query["assigned_to"] = assigned_to
    if priority:
        query["priority"] = priority
    if overdue_only:
        query["due_date"] = {"$lt": datetime.now(timezone.utc).isoformat()}
        query["status"] = {"$nin": ["completed", "cancelled"]}

    total = await db.tasks.count_documents(query)
    cursor = db.tasks.find(query).sort("due_date", 1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def update_task(db: AsyncIOMotorDatabase, task_id: str, data: Dict) -> Optional[Dict]:
    data["updated_at"] = datetime.now(timezone.utc)
    if data.get("status") == "completed" and "completed_at" not in data:
        data["completed_at"] = datetime.now(timezone.utc)
    try:
        result = await db.tasks.find_one_and_update(
            {"_id": ObjectId(task_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result) if result else None
    except Exception:
        return None


async def delete_task(db: AsyncIOMotorDatabase, task_id: str) -> bool:
    try:
        result = await db.tasks.delete_one({"_id": ObjectId(task_id)})
        return result.deleted_count > 0
    except Exception:
        return False


class TaskService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict, user_id: Optional[str] = None) -> Dict:
        return await create_task(self.db, data, user_id)

    async def get_by_id(self, task_id: str) -> Optional[Dict]:
        return await get_task(self.db, task_id)

    async def list(self, skip: int = 0, limit: int = 50, lead_id: Optional[str] = None, assigned_to: Optional[str] = None, status: Optional[str] = None, priority: Optional[str] = None, overdue_only: bool = False) -> Tuple[List[Dict], int]:
        return await list_tasks(self.db, skip, limit, lead_id, assigned_to, status, priority, overdue_only)

    async def update(self, task_id: str, data: Dict) -> Optional[Dict]:
        return await update_task(self.db, task_id, data)

    async def delete(self, task_id: str) -> bool:
        return await delete_task(self.db, task_id)

