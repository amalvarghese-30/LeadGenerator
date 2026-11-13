from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.lead import CRM_STAGES
from app.services.scoring_service import calculate_lead_score


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def create_lead(db: AsyncIOMotorDatabase, data: Dict, user_id: Optional[str] = None) -> Dict:
    now = datetime.now(timezone.utc)
    # Check for duplicate contact+company combo
    existing = await db.leads.find_one({
        "contact_id": data["contact_id"],
        "company_id": data.get("company_id"),
    })
    if existing:
        return _doc_to_dict(existing)

    doc = {
        **data,
        "crm_stage": "discovered",
        "lead_score": 0.0,
        "lead_priority": data.get("lead_priority", "medium"),
        "qualification_status": "unqualified",
        "outreach_eligible": False,
        "follow_up_count": 0,
        "score_breakdown": {},
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.leads.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc)


async def get_lead(db: AsyncIOMotorDatabase, lead_id: str) -> Optional[Dict]:
    try:
        doc = await db.leads.find_one({"_id": ObjectId(lead_id)})
        return _doc_to_dict(doc) if doc else None
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
        return _doc_to_dict(result) if result else None
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

    lead = await get_lead(db, lead_id)
    if not lead:
        return None

    old_stage = lead.get("crm_stage")
    now = datetime.now(timezone.utc)
    update_data = {
        "crm_stage": new_stage,
        "previous_stage": old_stage,
        "stage_changed_at": now,
        "last_activity": now,
        "updated_at": now,
    }
    if new_stage == "do_not_contact":
        update_data["outreach_eligible"] = False
    if new_stage in ("qualified", "ready_for_outreach_review"):
        update_data["qualification_status"] = "qualified"
        update_data["outreach_eligible"] = new_stage == "ready_for_outreach_review"

    result = await db.leads.find_one_and_update(
        {"_id": ObjectId(lead_id)},
        {"$set": update_data},
        return_document=True,
    )
    # Record activity
    if result:
        await db.activities.insert_one({
            "activity_type": "status_change",
            "lead_id": lead_id,
            "from_stage": old_stage,
            "to_stage": new_stage,
            "description": reason,
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
        })
    return _doc_to_dict(result) if result else None


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
    """Recalculate and persist lead score."""
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

    async def create(self, contact_id: str, company_id: Optional[str] = None, lead_source: Optional[str] = None, initial_stage: str = "discovered", user_id: Optional[str] = None) -> Dict:
        data = {
            "contact_id": contact_id,
            "company_id": company_id,
            "lead_source": lead_source,
            "crm_stage": initial_stage,
        }
        return await create_lead(self.db, data, user_id)

    async def get_by_id(self, lead_id: str) -> Optional[Dict]:
        return await get_lead(self.db, lead_id)

    async def list(self, skip: int = 0, limit: int = 20, crm_stage: Optional[str] = None, owner: Optional[str] = None, lead_priority: Optional[str] = None, outreach_eligible: Optional[bool] = None, qualification_status: Optional[str] = None, sort_by: str = "created_at", sort_dir: int = -1) -> Tuple[List[Dict], int]:
        return await list_leads(self.db, skip, limit, crm_stage, owner, lead_priority, outreach_eligible, qualification_status, sort_by, sort_dir)

    async def update(self, lead_id: str, data: Dict) -> Optional[Dict]:
        return await update_lead(self.db, lead_id, data)

    async def delete(self, lead_id: str) -> bool:
        return await delete_lead(self.db, lead_id)

    async def change_stage(self, lead_id: str, new_stage: str, user_id: Optional[str] = None, note: Optional[str] = None) -> Optional[Dict]:
        return await transition_stage(self.db, lead_id, new_stage, user_id, note)

    async def qualify(self, lead_id: str, qualification_status: str = "qualified", user_id: Optional[str] = None, reason: Optional[str] = None) -> Optional[Dict]:
        return await qualify_lead(self.db, lead_id, qualification_status, user_id, reason)

