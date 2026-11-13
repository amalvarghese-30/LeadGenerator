from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.deduplication import generate_contact_dedup_key


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_contact(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Tuple[Dict, bool]:
    """Returns (contact_dict, was_created)."""
    now = datetime.now(timezone.utc)
    urls = data.get("professional_urls", {})
    contacts_dict = data.get("business_contacts", {})
    dedup_key = generate_contact_dedup_key(
        full_name=data["full_name"],
        email=contacts_dict.get("email") or contacts_dict.get("work_email"),
        linkedin_url=urls.get("linkedin"),
        company_name=data.get("company_name"),
    )
    existing = await db.contacts.find_one({"dedup_key": dedup_key})
    if existing:
        return _doc_to_dict(existing), False

    doc = {
        **data,
        "dedup_key": dedup_key,
        "contact_verification_status": "unverified",
        "is_suppressed": False,
        "do_not_contact": False,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.contacts.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc), True


async def get_contact(db: AsyncIOMotorDatabase, contact_id: str) -> Optional[Dict]:
    try:
        doc = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


async def list_contacts(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    company_id: Optional[str] = None,
    is_suppressed: Optional[bool] = None,
    verification_status: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if search:
        query["$text"] = {"$search": search}
    if company_id:
        query["company_id"] = company_id
    if is_suppressed is not None:
        query["is_suppressed"] = is_suppressed
    if verification_status:
        query["contact_verification_status"] = verification_status

    total = await db.contacts.count_documents(query)
    cursor = db.contacts.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def update_contact(db: AsyncIOMotorDatabase, contact_id: str, data: Dict) -> Optional[Dict]:
    data["updated_at"] = datetime.now(timezone.utc)
    try:
        result = await db.contacts.find_one_and_update(
            {"_id": ObjectId(contact_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result) if result else None
    except Exception:
        return None


async def delete_contact(db: AsyncIOMotorDatabase, contact_id: str) -> bool:
    try:
        result = await db.contacts.delete_one({"_id": ObjectId(contact_id)})
        return result.deleted_count > 0
    except Exception:
        return False


async def suppress_contact(db: AsyncIOMotorDatabase, contact_id: str, reason: str) -> Optional[Dict]:
    return await update_contact(db, contact_id, {
        "is_suppressed": True,
        "do_not_contact": True,
        "suppression_reason": reason,
    })

class ContactService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict, user_id: Optional[str] = None):
        """Returns (contact_dict, was_created)."""
        return await create_contact(self.db, data, user_id)

    async def get_by_id(self, contact_id: str) -> Optional[Dict]:
        return await get_contact(self.db, contact_id)

    async def list(self, skip: int = 0, limit: int = 20, search: Optional[str] = None,
                   company_id: Optional[str] = None, is_suppressed: Optional[bool] = None,
                   verification_status: Optional[str] = None) -> Tuple[List[Dict], int]:
        return await list_contacts(self.db, skip, limit, search, company_id,
                                   is_suppressed, verification_status)

    async def update(self, contact_id: str, data: Dict) -> Optional[Dict]:
        return await update_contact(self.db, contact_id, data)

    async def delete(self, contact_id: str) -> bool:
        return await delete_contact(self.db, contact_id)

    async def suppress(self, contact_id: str, reason: str = "Requested") -> Optional[Dict]:
        return await suppress_contact(self.db, contact_id, reason)