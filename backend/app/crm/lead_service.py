"""
Lead Service - CRM Lead management and idempotent deduplication.
Fixes:
- Stable contact/company lead identifiers handling null company IDs safely
- Fully idempotent lead creation: re-running discovery crawls will NEVER duplicate leads
- Explicit creation flag: (lead_dict, was_created)
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.lead import CRM_STAGES
from app.services.scoring_service import calculate_lead_score
from app.utils.deduplication import generate_lead_dedup_key


def _doc_to_dict(doc: Optional[Dict]) -> Optional[Dict]:
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class LeadResult(dict):
    """Backwards-compatible dictionary for lead creation."""
    def __init__(self, lead_dict: Dict[str, Any], created: bool):
        super().__init__()
        self.update(lead_dict)
        self["lead"] = lead_dict
        self["created"] = created


async def create_lead(
    db: AsyncIOMotorDatabase, data: Dict[str, Any], user_id: Optional[str] = None
) -> LeadResult:
    """
    Idempotently create lead or return existing lead.
    Returns: LeadResult (behaves as dict with doc fields, plus res['created'] and res['lead'])
    """
    doc, was_created = await create_lead_with_status(db, data, user_id)
    return LeadResult(lead_dict=doc, created=was_created)


async def create_lead_with_status(
    db: AsyncIOMotorDatabase, data: Dict[str, Any], user_id: Optional[str] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    Idempotently create lead or return existing lead with an explicit boolean flag.
    Returns: (lead_dict, was_created)
    """
    now = datetime.now(timezone.utc)
    contact_id = str(data["contact_id"])
    company_id = str(data["company_id"]) if data.get("company_id") else None

    dedup_key = generate_lead_dedup_key(contact_id, company_id)

    # 1. Search for existing lead with null-safe query
    query: Dict[str, Any] = {
        "$or": [
            {"dedup_key": dedup_key},
            {"contact_id": contact_id, "company_id": company_id} if company_id else {
                "contact_id": contact_id,
                "$or": [{"company_id": None}, {"company_id": {"$exists": False}}]
            }
        ]
    }
    existing = await db.leads.find_one(query)
    if existing:
        return _doc_to_dict(existing), False

    # 2. Insert new lead
    doc = {
        **data,
        "contact_id": contact_id,
        "company_id": company_id,
        "dedup_key": dedup_key,
        "crm_stage": data.get("crm_stage", "discovered"),
        "lead_score": 0.0,
        "lead_priority": data.get("lead_priority", "medium"),
        "qualification_status": data.get("qualification_status", "unqualified"),
        "outreach_eligible": False,
        "follow_up_count": 0,
        "score_breakdown": {},
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.leads.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Compute initial lead score if possible
    contact = None
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    except Exception:
        pass
    score, breakdown = calculate_lead_score(doc, contact)
    await db.leads.update_one(
        {"_id": doc["_id"]},
        {"$set": {"lead_score": score, "score_breakdown": breakdown}}
    )
    doc["lead_score"] = score
    doc["score_breakdown"] = breakdown

    return _doc_to_dict(doc), True


async def get_lead(db: AsyncIOMotorDatabase, lead_id: str) -> Optional[Dict]:
    try:
        doc = await db.leads.find_one({"_id": ObjectId(lead_id)})
        return _doc_to_dict(doc)
    except Exception:
        return None


async def list_leads(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 20,
    crm_stage: Optional[str] = None,
    owner: Optional[str] = None,
    lead_priority: Optional[str] = None,
    outreach_eligible: Optional[bool] = None,
    qualification_status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: int = -1,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if crm_stage:
        query["crm_stage"] = crm_stage
    if owner:
        query["owner"] = owner
    if lead_priority:
        query["lead_priority"] = lead_priority
    if outreach_eligible is not None:
        query["outreach_eligible"] = outreach_eligible
    if qualification_status:
        query["qualification_status"] = qualification_status

    total = await db.leads.count_documents(query)
    cursor = db.leads.find(query).sort(sort_by, sort_dir).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_dict(d) for d in docs], total


async def update_lead(db: AsyncIOMotorDatabase, lead_id: str, data: Dict) -> Optional[Dict]:
    data["updated_at"] = datetime.now(timezone.utc)
    try:
        result = await db.leads.find_one_and_update(
            {"_id": ObjectId(lead_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result)
    except Exception:
        return None


async def transition_stage(
    db: AsyncIOMotorDatabase,
    lead_id: str,
    new_stage: str,
    user_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[Dict]:
    if new_stage not in CRM_STAGES:
        raise ValueError(f"Invalid CRM stage: {new_stage}")
    update_data: Dict[str, Any] = {
        "crm_stage": new_stage,
        "updated_at": datetime.now(timezone.utc),
    }
    if new_stage == "ready_for_outreach_review":
        update_data["outreach_eligible"] = True
    elif new_stage in ["disqualified", "closed", "do_not_contact"]:
        update_data["outreach_eligible"] = False
    return await update_lead(db, lead_id, update_data)


async def qualify_lead(
    db: AsyncIOMotorDatabase,
    lead_id: str,
    qualification_status: str,
    user_id: Optional[str] = None,
    disqualification_reason: Optional[str] = None,
) -> Optional[Dict]:
    update_data: Dict[str, Any] = {
        "qualification_status": qualification_status,
        "updated_at": datetime.now(timezone.utc),
    }
    if qualification_status == "disqualified":
        update_data["crm_stage"] = "disqualified"
        update_data["outreach_eligible"] = False
        update_data["disqualification_reason"] = disqualification_reason
    elif qualification_status == "qualified":
        update_data["crm_stage"] = "qualified"
    return await update_lead(db, lead_id, update_data)


async def recalculate_lead_score(db: AsyncIOMotorDatabase, lead_id: str) -> Optional[Dict]:
    lead = await get_lead(db, lead_id)
    if not lead:
        return None
    contact = None
    if lead.get("contact_id"):
        contact = await db.contacts.find_one({"_id": ObjectId(lead["contact_id"])})
    score, breakdown = calculate_lead_score(lead, contact)
    return await update_lead(db, lead_id, {"lead_score": score, "score_breakdown": breakdown})


class LeadService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(
        self,
        contact_id: str,
        company_id: Optional[str] = None,
        lead_source: Optional[str] = None,
        initial_stage: str = "discovered",
        user_id: Optional[str] = None,
    ) -> LeadResult:
        data = {
            "contact_id": contact_id,
            "company_id": company_id,
            "lead_source": lead_source,
            "crm_stage": initial_stage,
        }
        doc, was_created = await create_lead_with_status(self.db, data, user_id)
        return LeadResult(lead_dict=doc, created=was_created)

    async def get_by_id(self, lead_id: str) -> Optional[Dict]:
        return await get_lead(self.db, lead_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        crm_stage: Optional[str] = None,
        owner: Optional[str] = None,
        lead_priority: Optional[str] = None,
        outreach_eligible: Optional[bool] = None,
        qualification_status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: int = -1,
    ) -> Tuple[List[Dict], int]:
        return await list_leads(
            self.db, skip, limit, crm_stage, owner, lead_priority,
            outreach_eligible, qualification_status, sort_by, sort_dir
        )

    async def update(self, lead_id: str, data: Dict) -> Optional[Dict]:
        return await update_lead(self.db, lead_id, data)

    async def delete(self, lead_id: str) -> bool:
        try:
            result = await self.db.leads.delete_one({"_id": ObjectId(lead_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    async def change_stage(self, lead_id: str, new_stage: str, user_id: Optional[str] = None, note: Optional[str] = None) -> Optional[Dict]:
        return await transition_stage(self.db, lead_id, new_stage, user_id, note)

    async def qualify(self, lead_id: str, qualification_status: str = "qualified", user_id: Optional[str] = None, reason: Optional[str] = None) -> Optional[Dict]:
        return await qualify_lead(self.db, lead_id, qualification_status, user_id, reason)
