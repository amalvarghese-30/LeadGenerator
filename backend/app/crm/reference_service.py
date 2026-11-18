from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_reference(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Dict:
    now = datetime.now(timezone.utc)
    client_name = data.get("company_name") or data.get("client_name") or "Unknown Client"
    client_website = data.get("company_website") or data.get("client_website")
    source_url = data.get("source_url") or data.get("evidence_url")
    evidence_quote = data.get("evidence_quote") or data.get("evidence_snippet")
    conf = float(data.get("confidence") or data.get("confidence_score") or 0.8)

    doc = {
        **data,
        "client_name": client_name,
        "company_name": data.get("company_name") or client_name,
        "client_website": client_website,
        "company_website": data.get("company_website") or client_website,
        "source_url": source_url,
        "evidence_url": source_url,
        "evidence_snippet": evidence_quote,
        "evidence_quote": evidence_quote,
        "confidence": conf,
        "confidence_score": conf,
        "relationship_type": data.get("relationship_type") or "client_portfolio_reference",
        "reference_type": data.get("reference_type") or "client_portfolio_reference",
        "verification_status": data.get("verification_status", "pending_review"),
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.provider_client_references.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc)


async def get_reference(db: AsyncIOMotorDatabase, reference_id: str) -> Optional[Dict]:
    try:
        doc = await db.provider_client_references.find_one({"_id": ObjectId(reference_id)})
        return _doc_to_dict(doc) if doc else None
    except Exception:
        return None


async def list_references(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 50,
    provider_id: Optional[str] = None,
    verification_status: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if provider_id:
        query["provider_id"] = provider_id
    if verification_status:
        query["verification_status"] = verification_status

    total = await db.provider_client_references.count_documents(query)
    cursor = db.provider_client_references.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def verify_reference(
    db: AsyncIOMotorDatabase,
    reference_id: str,
    action: str,
    user_id: Optional[str] = None,
    rejection_reason: Optional[str] = None,
) -> Optional[Dict]:
    now = datetime.now(timezone.utc)
    update: Dict[str, Any] = {
        "verification_status": "verified" if action == "verify" else "rejected",
        "verified_by": user_id,
        "verified_at": now,
        "updated_at": now,
    }
    if rejection_reason:
        update["rejection_reason"] = rejection_reason
    try:
        result = await db.provider_client_references.find_one_and_update(
            {"_id": ObjectId(reference_id)},
            {"$set": update},
            return_document=True,
        )
        return _doc_to_dict(result) if result else None
    except Exception:
        return None


class ReferenceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict) -> Dict:
        return await create_reference(self.db, data)

    async def get_by_id(self, ref_id: str) -> Optional[Dict]:
        return await get_reference(self.db, ref_id)

    async def list(self, skip: int = 0, limit: int = 20, provider_id: Optional[str] = None, verification_status: Optional[str] = None) -> Tuple[List[Dict], int]:
        return await list_references(self.db, skip, limit, provider_id, verification_status)

    async def verify(self, ref_id: str, user_id: Optional[str] = None, notes: Optional[str] = None) -> Optional[Dict]:
        return await verify_reference(self.db, ref_id, "verify", user_id)

    async def reject(self, ref_id: str, reason: str = "Unsubstantiated", user_id: Optional[str] = None) -> Optional[Dict]:
        return await verify_reference(self.db, ref_id, "reject", user_id, reason)

