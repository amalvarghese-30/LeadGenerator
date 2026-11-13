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
        "dedup_key": dedup_key,
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
