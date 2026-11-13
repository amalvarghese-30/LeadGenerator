"""
Contact Service - CRM Contact management and deduplication.
Fixes:
- Reliable contact matching across: normalized full name, canonical LinkedIn profile, verified email, company association
- Preserves distinct individuals: do NOT merge same-named people across different companies
- Merges new evidence quotes and source references into existing contacts
- Explicit creation flag: (contact_dict, was_created)
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.deduplication import (
    generate_contact_dedup_key,
    normalize_string,
    normalize_linkedin_url,
)


def _doc_to_dict(doc: Optional[Dict]) -> Optional[Dict]:
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class ContactResult(dict):
    """Backwards-compatible dictionary for contact creation."""
    def __init__(self, contact_dict: Dict[str, Any], created: bool):
        super().__init__()
        self.update(contact_dict)
        self["contact"] = contact_dict
        self["created"] = created


async def create_contact(
    db: AsyncIOMotorDatabase, data: Dict[str, Any], user_id: Optional[str] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    Create contact or merge into existing contact record.
    Returns: (contact_dict, was_created)
    """
    now = datetime.now(timezone.utc)
    raw_name = (data.get("full_name") or "").strip()
    urls = data.get("professional_urls", {})
    contacts_dict = data.get("business_contacts", {})
    email = contacts_dict.get("email") or contacts_dict.get("work_email") or data.get("email")
    linkedin = urls.get("linkedin") or data.get("linkedin_url")
    company_name = data.get("company_name")
    company_id = data.get("company_id")
    new_refs = data.get("source_references") or []

    dedup_key = generate_contact_dedup_key(
        full_name=raw_name,
        email=email,
        linkedin_url=linkedin,
        company_name=company_name,
        company_id=company_id,
    )

    # 1. Search existing contact by strong keys
    queries: List[Dict[str, Any]] = [{"dedup_key": dedup_key}]
    if email and "@" in email:
        queries.append({"business_contacts.email": email.lower().strip()})
    if linkedin:
        li_handle = normalize_linkedin_url(linkedin)
        if li_handle:
            queries.append({"professional_urls.linkedin_handle": li_handle})

    existing = await db.contacts.find_one({"$or": queries})

    if existing:
        # Merge new references and missing fields into existing contact
        updates: Dict[str, Any] = {}
        if not existing.get("designation") and data.get("designation"):
            updates["designation"] = data["designation"]
        if not existing.get("company_id") and company_id:
            updates["company_id"] = company_id
        if not existing.get("company_name") and company_name:
            updates["company_name"] = company_name

        # Merge reference IDs
        update_op: Dict[str, Any] = {}
        if new_refs:
            update_op["$addToSet"] = {"source_references": {"$each": new_refs}}

        if updates:
            updates["updated_at"] = now
            update_op["$set"] = updates

        if update_op:
            await db.contacts.update_one({"_id": existing["_id"]}, update_op)
            updated_doc = await db.contacts.find_one({"_id": existing["_id"]})
            return _doc_to_dict(updated_doc), False

        return _doc_to_dict(existing), False

    # 2. Insert new contact record
    clean_li_handle = normalize_linkedin_url(linkedin) if linkedin else None
    prof_urls = dict(urls)
    if clean_li_handle:
        prof_urls["linkedin_handle"] = clean_li_handle

    doc = {
        **data,
        "full_name": raw_name,
        "normalized_name": normalize_string(raw_name),
        "dedup_key": dedup_key,
        "company_id": company_id,
        "company_name": company_name,
        "professional_urls": prof_urls,
        "source_references": list(set(new_refs)),
        "contact_verification_status": data.get("contact_verification_status", "unverified"),
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
        return _doc_to_dict(doc)
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
        return _doc_to_dict(result)
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

    async def create(self, data: Dict, user_id: Optional[str] = None) -> Tuple[Dict, bool]:
        """Returns (contact_dict, was_created)."""
        return await create_contact(self.db, data, user_id)

    async def get_by_id(self, contact_id: str) -> Optional[Dict]:
        return await get_contact(self.db, contact_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        company_id: Optional[str] = None,
        is_suppressed: Optional[bool] = None,
        verification_status: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        return await list_contacts(
            self.db, skip, limit, search, company_id, is_suppressed, verification_status
        )

    async def update(self, contact_id: str, data: Dict) -> Optional[Dict]:
        return await update_contact(self.db, contact_id, data)

    async def delete(self, contact_id: str) -> bool:
        return await delete_contact(self.db, contact_id)

    async def suppress(self, contact_id: str, reason: str = "Requested") -> Optional[Dict]:
        return await suppress_contact(self.db, contact_id, reason)
