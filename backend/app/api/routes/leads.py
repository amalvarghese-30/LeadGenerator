from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.lead_service import create_lead, get_lead, list_leads, update_lead, transition_stage, qualify_lead
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse, LeadStatusUpdate, LeadQualifyRequest
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/leads", tags=["Leads"])


def _fmt(doc: dict) -> dict:
    for f in ("created_at", "updated_at", "last_activity", "next_follow_up", "stage_changed_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc


@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_leads_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    crm_stage: Optional[str] = None,
    owner: Optional[str] = None,
    lead_priority: Optional[str] = None,
    outreach_eligible: Optional[bool] = None,
    qualification_status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: int = -1,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_leads(db, skip, limit, crm_stage, owner, lead_priority, outreach_eligible, qualification_status, sort_by, sort_dir)
    return paginate([_fmt(i) for i in items], total, page, limit)


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_lead_route(
    data: LeadCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await create_lead(db, data.model_dump(), str(user.get("_id", "")))
    return _fmt(doc)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead_route(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_lead(db, lead_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _fmt(doc)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead_route(
    lead_id: str,
    data: LeadUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await update_lead(db, lead_id, update_data)
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _fmt(doc)


@router.post("/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    lead_id: str,
    data: LeadStatusUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        doc = await transition_stage(db, lead_id, data.crm_stage, str(user.get("_id", "")), data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _fmt(doc)


@router.post("/{lead_id}/qualify", response_model=LeadResponse)
async def qualify_lead_route(
    lead_id: str,
    data: LeadQualifyRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await qualify_lead(db, lead_id, data.qualification_status, str(user.get("_id", "")), data.disqualification_reason)
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _fmt(doc)
