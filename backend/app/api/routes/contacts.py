from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.contact_service import create_contact, get_contact, list_contacts, update_contact, delete_contact, suppress_contact
from app.schemas.contact import ContactCreate, ContactUpdate, ContactResponse
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/contacts", tags=["Contacts"])

def _fmt(doc: dict) -> dict:
    for f in ("created_at", "updated_at", "verified_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc

@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_contacts_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = None,
    company_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    is_suppressed: Optional[bool] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_contacts(db, skip, limit, search, company_id, is_suppressed, verification_status)
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
