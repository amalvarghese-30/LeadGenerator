from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.crm.contact_service import (
    create_contact,
    get_contact,
    list_contacts,
    update_contact,
    delete_contact,
    suppress_contact,
    add_contact_channel,
    verify_contact_channel,
    reject_contact_channel,
)
from app.enrichment.contact_enrichment_service import ContactEnrichmentService
from app.schemas.contact import ContactCreate, ContactUpdate, ContactResponse, ContactChannelSchema
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/contacts", tags=["Contacts"])
enrichment_service = ContactEnrichmentService()


class BatchEnrichRequest(BaseModel):
    contact_ids: List[str]


class RejectChannelRequest(BaseModel):
    reason: str = "Rejected by reviewer"


def _fmt(doc: dict) -> dict:
    if not doc:
        return doc
    for f in ("created_at", "updated_at", "verified_at", "last_enriched_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    # Format channel datetime fields
    for ch in doc.get("contact_channels", []):
        for f in ("collected_at", "last_checked_at"):
            if ch.get(f) and hasattr(ch[f], "isoformat"):
                ch[f] = ch[f].isoformat()
    return doc


@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_contacts_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = None,
    company_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    enrichment_status: Optional[str] = None,
    is_suppressed: Optional[bool] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_contacts(
        db, skip, limit, search, company_id, is_suppressed, verification_status, enrichment_status
    )
    return paginate([_fmt(i) for i in items], total, page, limit)


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_contact_route(
    data: ContactCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc, _ = await create_contact(db, data.model_dump(), str(user.get("_id", "")))
    return _fmt(doc)


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact_route(
    contact_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_contact(db, contact_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _fmt(doc)


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact_route(
    contact_id: str,
    data: ContactUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await update_contact(db, contact_id, updates)
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _fmt(doc)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_route(
    contact_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    success = await delete_contact(db, contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")


@router.post("/{contact_id}/suppress", response_model=ContactResponse)
async def suppress_contact_route(
    contact_id: str,
    reason: str = Query("Do-not-contact request"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await suppress_contact(db, contact_id, reason)
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _fmt(doc)


# ----------------------------------------------------------------------
# Contact Enrichment Endpoints
# ----------------------------------------------------------------------

@router.post("/{contact_id}/enrich")
async def enrich_single_contact_route(
    contact_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Trigger the Contact Enrichment Engine for a single contact."""
    result = await enrichment_service.enrich_contact(db, contact_id)
    updated_doc = await get_contact(db, contact_id)
    return {
        "summary": result,
        "contact": _fmt(updated_doc),
    }


@router.post("/enrich-batch")
async def enrich_batch_route(
    req: BatchEnrichRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Trigger enrichment on multiple contacts in parallel."""
    results = await enrichment_service.enrich_contacts_batch(db, req.contact_ids)
    return {"results": results, "total": len(results)}


@router.post("/{contact_id}/channels", response_model=ContactResponse)
async def add_channel_route(
    contact_id: str,
    channel: ContactChannelSchema,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Manually add a missing contact channel with source provenance."""
    doc = await add_contact_channel(db, contact_id, channel.model_dump())
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _fmt(doc)


@router.post("/{contact_id}/channels/{channel_index}/verify", response_model=ContactResponse)
async def verify_channel_route(
    contact_id: str,
    channel_index: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Human review action: verify a specific contact channel."""
    doc = await verify_contact_channel(db, contact_id, channel_index, str(user.get("_id", "admin")))
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _fmt(doc)


@router.post("/{contact_id}/channels/{channel_index}/reject", response_model=ContactResponse)
async def reject_channel_route(
    contact_id: str,
    channel_index: int,
    req: RejectChannelRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Human review action: reject an incorrect or bounced contact channel."""
    doc = await reject_contact_channel(
        db, contact_id, channel_index, str(user.get("_id", "admin")), reason=req.reason
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _fmt(doc)
