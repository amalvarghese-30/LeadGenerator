from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.activity_service import create_activity, get_activity, list_activities, update_activity
from app.schemas.activity import ActivityCreate, ActivityUpdate, ActivityResponse
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/activities", tags=["Activities"])

def _fmt(doc: dict) -> dict:
    for f in ("created_at", "updated_at", "scheduled_at", "completed_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc

@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_activities_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    lead_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    company_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    activity_type: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_activities(db, skip, limit, lead_id, contact_id, company_id, provider_id, activity_type)
    return paginate([_fmt(i) for i in items], total, page, limit)

@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_activity_route(
    data: ActivityCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await create_activity(db, data.model_dump(), str(user.get("_id", "")))
    return _fmt(doc)

@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity_route(
    activity_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_activity(db, activity_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Activity not found")
    return _fmt(doc)

@router.patch("/{activity_id}", response_model=ActivityResponse)
async def update_activity_route(
    activity_id: str,
    data: ActivityUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await update_activity(db, activity_id, updates)
    if not doc:
        raise HTTPException(status_code=404, detail="Activity not found")
    return _fmt(doc)
