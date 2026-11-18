"""
Company Service - CRM Company management and deduplication.
Fixes:
- Explicit new-vs-existing company creation detection: {"company": {...}, "created": true/false}
- Multi-signal deduplication across: domain, canonical website, LinkedIn company URL, normalized name
- Accurate statistics updates without overwriting existing data
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.deduplication import (
    generate_company_dedup_key,
    normalize_domain,
    normalize_company_name,
)
from app.utils.url_utils import extract_domain


def _doc_to_dict(doc: Optional[Dict]) -> Optional[Dict]:
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class CompanyResult(dict):
    """
    Backwards-compatible dictionary response for company creation.
    Provides:
      res["company"]: dict
      res["created"]: bool
      res["id"]: direct access to company id
      res["name"]: direct access to company name
    """
    def __init__(self, company_dict: Dict[str, Any], created: bool):
        super().__init__()
        # Populate with company fields directly for backward compatibility
        self.update(company_dict)
        # Explicit keys required by Task 7
        self["company"] = company_dict
        self["created"] = created


async def create_company(
    db: AsyncIOMotorDatabase, data: Dict[str, Any], user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create company or return existing record."""
    res, _ = await create_company_with_status(db, data, user_id)
    return res


async def create_company_with_status(
    db: AsyncIOMotorDatabase, data: Dict[str, Any], user_id: Optional[str] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    Create company or return existing record with an explicit created flag.
    Returns: (company_dict, was_created)
    """
    now = datetime.now(timezone.utc)
    raw_name = (data.get("name") or "").strip()
    website = data.get("website")
    domain = normalize_domain(data.get("domain") or website or extract_domain(website or ""))
    linkedin = data.get("linkedin_url")
    norm_name = normalize_company_name(raw_name)

    dedup_key = generate_company_dedup_key(
        name=raw_name,
        domain=domain,
        website=website,
        linkedin_url=linkedin,
    )

    # 1. Search for existing company across multiple high-confidence signals
    queries = [{"dedup_key": dedup_key}]
    if domain:
        queries.append({"domain": domain})
    if linkedin:
        queries.append({"linkedin_url": linkedin})
    if norm_name and len(norm_name) >= 3:
        queries.append({"normalized_name": norm_name})

    existing = await db.companies.find_one({"$or": queries})
    if existing:
        # Merge new fields if existing record is missing them
        updates: Dict[str, Any] = {}
        if not existing.get("industry") and data.get("industry"):
            updates["industry"] = data["industry"]
        if not existing.get("domain") and domain:
            updates["domain"] = domain
        if not existing.get("website") and website:
            updates["website"] = website
        if not existing.get("linkedin_url") and linkedin:
            updates["linkedin_url"] = linkedin
        if not existing.get("description") and data.get("description"):
            updates["description"] = data["description"]
        if not existing.get("address") and data.get("address"):
            updates["address"] = data["address"]
        if not existing.get("country") and data.get("country"):
            updates["country"] = data["country"]
        if not existing.get("city") and data.get("city"):
            updates["city"] = data["city"]
        if not existing.get("state") and data.get("state"):
            updates["state"] = data["state"]

        # Merge aliases
        existing_aliases = set(existing.get("aliases") or [])
        new_aliases = [a for a in (data.get("aliases") or []) if a and a not in existing_aliases]
        if new_aliases:
            updates["aliases"] = list(existing_aliases.union(new_aliases))

        # Merge associated_people without duplicates by normalized name
        existing_people = existing.get("associated_people") or []
        existing_p_names = {p.get("full_name", "").strip().lower() for p in existing_people if isinstance(p, dict)}
        new_people = [p for p in (data.get("associated_people") or []) if isinstance(p, dict) and p.get("full_name", "").strip().lower() not in existing_p_names]
        if new_people:
            updates["associated_people"] = existing_people + new_people

        # Merge public contact info if missing
        curr_contact = dict(existing.get("public_contact") or {})
        new_contact = data.get("public_contact") or {}
        merged_contact = {**new_contact, **curr_contact}
        if merged_contact != curr_contact:
            updates["public_contact"] = merged_contact

        # Merge public_contact_channels without duplicates
        existing_channels = existing.get("public_contact_channels") or []
        existing_vals = {c.get("value") for c in existing_channels if isinstance(c, dict) and c.get("value")}
        new_channels = [c for c in (data.get("public_contact_channels") or []) if isinstance(c, dict) and c.get("value") not in existing_vals]
        if new_channels:
            updates["public_contact_channels"] = existing_channels + new_channels

        # Merge social_profiles without duplicates
        existing_socials = existing.get("social_profiles") or []
        existing_s_urls = {s.get("url") for s in existing_socials if isinstance(s, dict) and s.get("url")}
        new_socials = [s for s in (data.get("social_profiles") or []) if isinstance(s, dict) and s.get("url") not in existing_s_urls]
        if new_socials:
            updates["social_profiles"] = existing_socials + new_socials

        # Merge source_references
        existing_refs = set(existing.get("source_references") or [])
        new_refs = [r for r in (data.get("source_references") or []) if r and r not in existing_refs]
        if new_refs:
            updates["source_references"] = list(existing_refs.union(new_refs))

        if updates:
            updates["updated_at"] = now
            await db.companies.update_one({"_id": existing["_id"]}, {"$set": updates})
            existing.update(updates)

        return _doc_to_dict(existing), False

    # 2. Insert new company
    doc = {
        **data,
        "name": raw_name,
        "normalized_name": norm_name,
        "domain": domain,
        "website": website,
        "dedup_key": dedup_key,
        "public_contact": data.get("public_contact") or {},
        "public_contact_channels": data.get("public_contact_channels") or [],
        "social_profiles": data.get("social_profiles") or [],
        "associated_people": data.get("associated_people") or [],
        "aliases": data.get("aliases") or [],
        "address": data.get("address"),
        "description": data.get("description"),
        "enrichment_status": data.get("enrichment_status", "pending"),
        "enrichment_attempts": data.get("enrichment_attempts", 0),
        "source_references": data.get("source_references") or [],
        "verification_status": data.get("verification_status", "unverified"),
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.companies.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_dict(doc), True


async def get_company(db: AsyncIOMotorDatabase, company_id: str) -> Optional[Dict]:
    try:
        doc = await db.companies.find_one({"_id": ObjectId(company_id)})
        return _doc_to_dict(doc)
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
        return _doc_to_dict(result)
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

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> CompanyResult:
        """
        Creates or retrieves existing company.
        Returns CompanyResult with:
          res["company"]: dict
          res["created"]: bool
        """
        doc, was_created = await create_company_with_status(self.db, data, user_id)
        return CompanyResult(company_dict=doc, created=was_created)

    async def get_by_id(self, company_id: str) -> Optional[Dict]:
        return await get_company(self.db, company_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        return await list_companies(self.db, skip, limit, search, industry, country)

    async def update(self, company_id: str, data: Dict) -> Optional[Dict]:
        return await update_company(self.db, company_id, data)

    async def delete(self, company_id: str) -> bool:
        return await delete_company(self.db, company_id)
