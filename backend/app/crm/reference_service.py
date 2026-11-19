from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
import hashlib
import re


def _doc_to_dict(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def _normalise_identity(value: Optional[str]) -> str:
    if not value or not isinstance(value, str):
        return ""
    return " ".join(value.split()).casefold()


def _make_dedup_key(
    provider_id: str,
    source_url: str,
    person_name: str,
    company_name: str,
) -> str:
    identity = (
        f"person:{person_name}|company:{company_name}"
        if person_name
        else f"company:{company_name}"
    )
    raw = "|".join((
        provider_id.strip(),
        source_url.strip().rstrip("/"),
        identity,
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()



def _reference_fill_expression(field, value, empty_is_missing=False):
    current = f"${field}"
    if empty_is_missing:
        condition = {
            "$in": [{"$ifNull": [current, ""]}, ["", None]]
        }
    else:
        condition = {
            "$eq": [{"$ifNull": [current, None]}, None]
        }

    return {
        "$cond": [
            condition,
            {"$literal": value},
            current
        ]
    }


def _reference_update_pipeline(doc, dedup_key, now, confidence, user_id):
    fill_empty_fields = {
        "person_name", "designation", "company_name", "client_name",
        "company_website", "client_website", "evidence_quote",
        "evidence_snippet", "relationship_type", "reference_type",
        "source_url", "evidence_url"
    }

    fields = {}

    for field, value in doc.items():
        if field in {
            "_id", "dedup_key", "created_at", "created_by",
            "verification_status", "last_seen_at", "updated_at",
            "confidence", "confidence_score"
        }:
            continue
        if field.startswith("$") or "." in field:
            continue

        fields[field] = _reference_fill_expression(
            field, value, field in fill_empty_fields
        )

    fields.update({
        "dedup_key": {"$literal": dedup_key},
        "created_at": _reference_fill_expression("created_at", now),
        "created_by": _reference_fill_expression("created_by", user_id),
        "verification_status": _reference_fill_expression(
            "verification_status",
            doc.get("verification_status", "pending_review"),
            True
        ),
        "last_seen_at": {"$literal": now},
        "updated_at": {"$literal": now},
        "confidence": {
            "$max": [{"$ifNull": ["$confidence", 0]}, {"$literal": confidence}]
        },
        "confidence_score": {
            "$max": [
                {"$ifNull": ["$confidence_score", 0]},
                {"$literal": confidence}
            ]
        }
    })

    return [{"$set": fields}]


async def create_reference(
    db: AsyncIOMotorDatabase,
    data: Dict,
    user_id: Optional[str] = None,
) -> Dict:
    now = datetime.now(timezone.utc)

    provider_id = str(data.get("provider_id") or "").strip()
    person_name = data.get("person_name")
    company_name = data.get("company_name") or data.get("client_name")

    person_key = _normalise_identity(person_name)
    company_key = _normalise_identity(company_name)

    if not provider_id:
        raise ValueError("provider_id is required")
    if not person_key and not company_key:
        raise ValueError("A reference must contain a person or company identity")

    source_url = data.get("source_url") or data.get("evidence_url")
    source_url = source_url.strip() if isinstance(source_url, str) else None

    evidence_quote = data.get("evidence_quote") or data.get("evidence_snippet")
    client_website = data.get("company_website") or data.get("client_website")

    raw_confidence = data.get("confidence")
    if raw_confidence is None:
        raw_confidence = data.get("confidence_score")
    if raw_confidence is None:
        raw_confidence = 0.8

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    relationship = (
        data.get("relationship_type")
        or data.get("reference_type")
        or "unclear_relationship"
    )

    doc = {
        **data,
        "provider_id": provider_id,
        "person_name": person_name,
        "designation": data.get("designation"),
        "client_name": company_name or None,
        "company_name": company_name or None,
        "client_website": client_website,
        "company_website": client_website,
        "source_url": source_url,
        "evidence_url": source_url,
        "evidence_snippet": evidence_quote,
        "evidence_quote": evidence_quote,
        "confidence": confidence,
        "confidence_score": confidence,
        "relationship_type": relationship,
        "reference_type": data.get("reference_type") or relationship,
        "verification_status": data.get("verification_status") or "pending_review",
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
        "last_seen_at": now,
    }

    collection = db.provider_client_references

    # Without a source page, preserve the existing non-deduplicated behavior.
    if not source_url:
        result = await collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        response = _doc_to_dict(doc)
        response["created"] = True
        return response

    dedup_key = _make_dedup_key(
        provider_id, source_url, person_key, company_key
    )
    doc["dedup_key"] = dedup_key

    pipeline = _reference_update_pipeline(
        doc, dedup_key, now, confidence, user_id
    )

    # Retain legacy matching for URL/name variations.
    existing = await collection.find_one({"dedup_key": dedup_key})

    if not existing:
        legacy_query = {
            "provider_id": provider_id,
            "source_url": {
                "$regex": "^" + re.escape(source_url.rstrip("/")) + "/?$",
                "$options": "i",
            },
        }

        if person_key:
            legacy_query["person_name"] = {
                "$regex": "^" + re.escape(str(person_name).strip()) + "$",
                "$options": "i",
            }

        if company_key:
            company_match = {
                "$regex": "^" + re.escape(str(company_name).strip()) + "$",
                "$options": "i",
            }
            legacy_query["$or"] = [
                {"company_name": company_match},
                {"client_name": company_match},
            ]

        existing = await collection.find_one(legacy_query)

    if existing:
        try:
            await collection.update_one(
                {"_id": existing["_id"]}, pipeline, upsert=False
            )
        except DuplicateKeyError:
            # A canonical record may have been inserted concurrently.
            canonical = await collection.find_one({"dedup_key": dedup_key})
            if not canonical:
                raise
            await collection.update_one(
                {"dedup_key": dedup_key}, pipeline, upsert=False
            )

        stored = await collection.find_one({"dedup_key": dedup_key})
        if not stored:
            raise RuntimeError("Reference update completed but record was not found")

        response = _doc_to_dict(stored)
        response["created"] = False
        return response

    # Atomic insert-or-update. The unique index protects simultaneous upserts.
    try:
        result = await collection.update_one(
            {"dedup_key": dedup_key},
            pipeline,
            upsert=True
        )
        created = result.upserted_id is not None
    except DuplicateKeyError:
        # Another worker won the insert race. Update its record instead.
        retry = await collection.update_one(
            {"dedup_key": dedup_key},
            pipeline,
            upsert=False
        )
        if retry.matched_count != 1:
            raise
        created = False

    stored = await collection.find_one({"dedup_key": dedup_key})
    if not stored:
        raise RuntimeError("Reference upsert completed but record was not found")

    response = _doc_to_dict(stored)
    response["created"] = created
    return response


async def get_reference(
    db: AsyncIOMotorDatabase,
    reference_id: str,
) -> Optional[Dict]:
    try:
        doc = await db.provider_client_references.find_one(
            {"_id": ObjectId(reference_id)}
        )
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

    cursor = (
        db.provider_client_references.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

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

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        provider_id: Optional[str] = None,
        verification_status: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        return await list_references(
            self.db, skip, limit, provider_id, verification_status
        )

    async def verify(
        self,
        ref_id: str,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        return await verify_reference(self.db, ref_id, "verify", user_id)

    async def reject(
        self,
        ref_id: str,
        reason: str = "Unsubstantiated",
        user_id: Optional[str] = None,
    ) -> Optional[Dict]:
        return await verify_reference(
            self.db, ref_id, "reject", user_id, reason
        )
