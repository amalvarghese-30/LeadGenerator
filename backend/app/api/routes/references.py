from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.reference_service import create_reference, get_reference, list_references, verify_reference
from app.schemas.reference import ReferenceCreate, ReferenceVerify, ReferenceResponse
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/references", tags=["References"])

def _fmt(doc: dict) -> dict:
    for f in ("created_at", "updated_at", "verified_at", "published_date", "collected_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc

@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_references_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    provider_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_references(db, skip, limit, provider_id, verification_status)
    return paginate([_fmt(i) for i in items], total, page, limit)

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_reference_route(
    data: ReferenceCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await create_reference(db, data.model_dump())
    return _fmt(doc)

@router.get("/{reference_id}")
async def get_reference_route(
    reference_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_reference(db, reference_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference not found")
    return _fmt(doc)

@router.post("/{reference_id}/verify")
async def verify_reference_route(
    reference_id: str,
    data: Optional[ReferenceVerify] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = str(user.get("_id", ""))
    action = data.action if data else "verify"
    rejection_reason = data.rejection_reason if data else None
    doc = await verify_reference(db, reference_id, action, user_id, rejection_reason)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference not found")
    return _fmt(doc)

@router.post("/{reference_id}/reject")
async def reject_reference_route(
    reference_id: str,
    reason: str = Query("Evidence does not confirm direct client relationship"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = str(user.get("_id", ""))
    doc = await verify_reference(db, reference_id, "reject", user_id, reason)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference not found")
    return _fmt(doc)
