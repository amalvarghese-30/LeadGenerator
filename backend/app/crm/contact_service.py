"""
Contact Service - CRM Contact management, deduplication, and contact channel operations.
Features:
- Multi-signal deduplication: normalized full name, canonical LinkedIn profile, verified email, company association
- Preserves distinct individuals: do NOT merge same-named people across different companies
- Merges new evidence quotes, source references, and contact channels into existing contacts
- Rich contact channel support (email, phone, form, social, website) with source provenance
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


def _merge_channels(existing_channels: List[Dict], new_channels: List[Dict]) -> List[Dict]:
    """Merge new contact channels into existing ones avoiding duplicate values."""
    by_val: Dict[str, Dict] = {}
    for ch in existing_channels:
        key = f"{ch.get('type')}:{ch.get('value', '').lower().strip()}"
        by_val[key] = ch

    for ch in new_channels:
        key = f"{ch.get('type')}:{ch.get('value', '').lower().strip()}"
        if key not in by_val:
            by_val[key] = ch
        else:
            # Upgrade verification status if new status is higher confidence
            curr = by_val[key]
            status_order = ["not_found", "discovered", "published", "format_checked", "source_verified", "human_reviewed"]
            curr_rank = status_order.index(curr.get("verification_status", "discovered")) if curr.get("verification_status") in status_order else 0
            new_rank = status_order.index(ch.get("verification_status", "discovered")) if ch.get("verification_status") in status_order else 0
            if new_rank > curr_rank:
                curr["verification_status"] = ch.get("verification_status")
                curr["confidence"] = max(curr.get("confidence", 0.5), ch.get("confidence", 0.5))
            if not curr.get("evidence_quote") and ch.get("evidence_quote"):
                curr["evidence_quote"] = ch["evidence_quote"]
            if not curr.get("source_url") and ch.get("source_url"):
                curr["source_url"] = ch["source_url"]

    return list(by_val.values())


async def create_contact(
    db: AsyncIOMotorDatabase, data: Dict[str, Any], user_id: Optional[str] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    Create contact or merge into existing contact record.
    Returns: (contact_dict, was_created)
    """
    now = datetime.now(timezone.utc)
    raw_name = (data.get("full_name") or "").strip()
    urls = dict(data.get("professional_urls", {}))
    contacts_dict = dict(data.get("business_contacts", {}))
    email = contacts_dict.get("email") or contacts_dict.get("work_email") or data.get("email")
    phone = contacts_dict.get("phone") or contacts_dict.get("mobile") or data.get("phone")
    linkedin = urls.get("linkedin") or data.get("linkedin_url")
    company_name = data.get("company_name")
    company_id = data.get("company_id")
    new_refs = data.get("source_references") or []
    new_channels = data.get("contact_channels") or []

    # If top-level email or phone provided, ensure they exist in business_contacts and contact_channels
    if email and "email" not in contacts_dict:
        contacts_dict["email"] = email
    if phone and "phone" not in contacts_dict:
        contacts_dict["phone"] = phone
    if linkedin and "linkedin" not in urls:
        urls["linkedin"] = linkedin

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
        queries.append({"contact_channels.value": email.lower().strip()})
    if linkedin:
        li_handle = normalize_linkedin_url(linkedin)
        if li_handle:
            queries.append({"professional_urls.linkedin_handle": li_handle})

    existing = await db.contacts.find_one({"$or": queries})

    if existing:
        # Merge new references, missing fields, and channels into existing contact
        updates: Dict[str, Any] = {}
        if not existing.get("designation") and data.get("designation"):
            updates["designation"] = data["designation"]
        if not existing.get("company_id") and company_id:
            updates["company_id"] = company_id
        if not existing.get("company_name") and company_name:
            updates["company_name"] = company_name

        # Preserve multi-company associations
        assoc_comps = list(existing.get("associated_companies") or [])
        if existing.get("company_id") and not any(ac.get("company_id") == existing["company_id"] for ac in assoc_comps if isinstance(ac, dict)):
            assoc_comps.append({
                "company_id": existing.get("company_id"),
                "company_name": existing.get("company_name"),
                "designation": existing.get("designation"),
            })
        if company_id and not any(ac.get("company_id") == company_id for ac in assoc_comps if isinstance(ac, dict)):
            assoc_comps.append({
                "company_id": company_id,
                "company_name": company_name,
                "designation": data.get("designation"),
            })
            updates["associated_companies"] = assoc_comps

        # Merge business_contacts
        merged_contacts = dict(existing.get("business_contacts", {}))
        for k, v in contacts_dict.items():
            if v and not merged_contacts.get(k):
                merged_contacts[k] = v
        if merged_contacts != existing.get("business_contacts", {}):
            updates["business_contacts"] = merged_contacts
            if merged_contacts.get("email") and not existing.get("email"):
                updates["email"] = merged_contacts["email"]
            if merged_contacts.get("phone") and not existing.get("phone"):
                updates["phone"] = merged_contacts["phone"]

        # Merge professional_urls
        merged_urls = dict(existing.get("professional_urls", {}))
        for k, v in urls.items():
            if v and not merged_urls.get(k):
                merged_urls[k] = v
        if merged_urls != existing.get("professional_urls", {}):
            updates["professional_urls"] = merged_urls
            if merged_urls.get("linkedin") and not existing.get("linkedin_url"):
                updates["linkedin_url"] = merged_urls["linkedin"]

        # Merge contact_channels
        if new_channels:
            merged_ch = _merge_channels(existing.get("contact_channels", []), new_channels)
            updates["contact_channels"] = merged_ch

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
        "associated_companies": data.get("associated_companies") or ([{"company_id": company_id, "company_name": company_name, "designation": data.get("designation")}] if company_id else []),
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin,
        "professional_urls": prof_urls,
        "business_contacts": contacts_dict,
        "contact_channels": new_channels,
        "source_references": list(set(new_refs)),
        "contact_verification_status": data.get("contact_verification_status", "discovered"),
        "enrichment_status": data.get("enrichment_status", "not_started"),
        "enrichment_attempts": 0,
        "enrichment_errors": [],
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
    enrichment_status: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    query: Dict[str, Any] = {}
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"company_name": {"$regex": search, "$options": "i"}},
            {"designation": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"business_contacts.email": {"$regex": search, "$options": "i"}},
        ]
    if company_id:
        query["company_id"] = company_id
    if is_suppressed is not None:
        if is_suppressed is False:
            query["is_suppressed"] = {"$ne": True}
        else:
            query["is_suppressed"] = True
    if verification_status:
        query["contact_verification_status"] = verification_status
    if enrichment_status:
        query["enrichment_status"] = enrichment_status

    total = await db.contacts.count_documents(query)
    cursor = db.contacts.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    contact_list = [_doc_to_dict(d) for d in docs]

    # Join associated company information to ensure full contact channels are populated
    for c in contact_list:
        comp_id = c.get("company_id")
        comp = None
        if comp_id and ObjectId.is_valid(comp_id):
            comp = await db.companies.find_one({"_id": ObjectId(comp_id)})
        elif c.get("company_name"):
            comp = await db.companies.find_one({"name": c["company_name"]})

        if comp:
            if not c.get("website"):
                c["website"] = comp.get("website")
            if not c.get("company_website"):
                c["company_website"] = comp.get("website")
            if not c.get("emails"):
                c["emails"] = comp.get("emails") or ([c["email"]] if c.get("email") else [])
            if not c.get("phones"):
                c["phones"] = comp.get("phones") or ([c["phone"]] if c.get("phone") else [])
            if not c.get("socials"):
                c["socials"] = dict(comp.get("socials") or {})
                if c.get("linkedin_url") and not c["socials"].get("linkedin"):
                    c["socials"]["linkedin"] = c["linkedin_url"]
        else:
            if not c.get("emails") and c.get("email"):
                c["emails"] = [c["email"]]
            if not c.get("phones") and c.get("phone"):
                c["phones"] = [c["phone"]]
            if not c.get("socials"):
                c["socials"] = {
                    "linkedin": c.get("linkedin_url"),
                    "instagram": None,
                    "facebook": None,
                    "twitter": None,
                    "youtube": None,
                }

    return contact_list, total


async def update_contact(
    db: AsyncIOMotorDatabase, contact_id: str, data: Dict[str, Any]
) -> Optional[Dict]:
    try:
        data["updated_at"] = datetime.now(timezone.utc)
        result = await db.contacts.find_one_and_update(
            {"_id": ObjectId(contact_id)},
            {"$set": data},
            return_document=True,
        )
        return _doc_to_dict(result)
    except Exception:
        return None


async def add_contact_channel(
    db: AsyncIOMotorDatabase, contact_id: str, channel: Dict[str, Any]
) -> Optional[Dict]:
    """Add or update an individual contact channel on a contact record."""
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            return None

        channels = contact.get("contact_channels", [])
        updated_channels = _merge_channels(channels, [channel])

        updates: Dict[str, Any] = {
            "contact_channels": updated_channels,
            "updated_at": datetime.now(timezone.utc),
        }

        # Sync top-level fields for direct contacts
        ch_type = channel.get("type")
        val = channel.get("value")
        scope = channel.get("scope")

        if ch_type == "email" and val:
            b_contacts = dict(contact.get("business_contacts", {}))
            if scope == "person_direct_work" or "email" not in b_contacts:
                b_contacts["email"] = val
                updates["email"] = val
                updates["business_contacts"] = b_contacts
        elif ch_type == "phone" and val:
            b_contacts = dict(contact.get("business_contacts", {}))
            if scope == "person_direct_work" or "phone" not in b_contacts:
                b_contacts["phone"] = val
                updates["phone"] = val
                updates["business_contacts"] = b_contacts

        result = await db.contacts.find_one_and_update(
            {"_id": ObjectId(contact_id)},
            {"$set": updates},
            return_document=True,
        )
        return _doc_to_dict(result)
    except Exception:
        return None


async def verify_contact_channel(
    db: AsyncIOMotorDatabase, contact_id: str, channel_index: int, user_id: str
) -> Optional[Dict]:
    """Human review action: marks a specific channel as human_reviewed."""
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            return None

        channels = contact.get("contact_channels", [])
        if 0 <= channel_index < len(channels):
            channels[channel_index]["human_reviewed"] = True
            channels[channel_index]["verification_status"] = "human_reviewed"
            channels[channel_index]["last_checked_at"] = datetime.now(timezone.utc)
            channels[channel_index]["notes"] = f"Verified by user {user_id}"

            result = await db.contacts.find_one_and_update(
                {"_id": ObjectId(contact_id)},
                {"$set": {"contact_channels": channels, "updated_at": datetime.now(timezone.utc)}},
                return_document=True,
            )
            return _doc_to_dict(result)
        return _doc_to_dict(contact)
    except Exception:
        return None


async def reject_contact_channel(
    db: AsyncIOMotorDatabase, contact_id: str, channel_index: int, user_id: str, reason: str = "Rejected by reviewer"
) -> Optional[Dict]:
    """Human review action: marks a specific channel as rejected."""
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            return None

        channels = contact.get("contact_channels", [])
        if 0 <= channel_index < len(channels):
            channels[channel_index]["verification_status"] = "rejected"
            channels[channel_index]["notes"] = f"Rejected: {reason} by {user_id}"
            channels[channel_index]["last_checked_at"] = datetime.now(timezone.utc)

            # If this was the active top-level email/phone, clear it
            ch_val = channels[channel_index].get("value")
            updates: Dict[str, Any] = {
                "contact_channels": channels,
                "updated_at": datetime.now(timezone.utc),
            }
            if contact.get("email") == ch_val:
                updates["email"] = None
            if contact.get("phone") == ch_val:
                updates["phone"] = None

            result = await db.contacts.find_one_and_update(
                {"_id": ObjectId(contact_id)},
                {"$set": updates},
                return_document=True,
            )
            return _doc_to_dict(result)
        return _doc_to_dict(contact)
    except Exception:
        return None


async def delete_contact(db: AsyncIOMotorDatabase, contact_id: str) -> bool:
    try:
        res = await db.contacts.delete_one({"_id": ObjectId(contact_id)})
        return res.deleted_count > 0
    except Exception:
        return False


async def suppress_contact(
    db: AsyncIOMotorDatabase, contact_id: str, reason: str = "Do-not-contact request"
) -> Optional[Dict]:
    try:
        result = await db.contacts.find_one_and_update(
            {"_id": ObjectId(contact_id)},
            {
                "$set": {
                    "is_suppressed": True,
                    "do_not_contact": True,
                    "suppression_reason": reason,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=True,
        )
        return _doc_to_dict(result)
    except Exception:
        return None


# Backwards compatibility aliases (do not alias 'list' to avoid shadowing Python's built-in list)
create = create_contact
get = get_contact
update = update_contact
delete = delete_contact
suppress = suppress_contact


class ContactService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Tuple[Dict[str, Any], bool]:
        return await create_contact(self.db, data, user_id)

    async def get_by_id(self, contact_id: str) -> Optional[Dict]:
        return await get_contact(self.db, contact_id)

    async def list(self, skip: int = 0, limit: int = 20, **kwargs) -> Tuple[List[Dict], int]:
        return await list_contacts(self.db, skip=skip, limit=limit, **kwargs)

    async def update(self, contact_id: str, data: Dict[str, Any]) -> Optional[Dict]:
        return await update_contact(self.db, contact_id, data)

    async def delete(self, contact_id: str) -> bool:
        return await delete_contact(self.db, contact_id)

    async def suppress(self, contact_id: str, reason: str = "Do-not-contact request") -> Optional[Dict]:
        return await suppress_contact(self.db, contact_id, reason)

