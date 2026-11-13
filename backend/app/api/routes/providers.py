from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.provider_service import create_provider, get_provider, list_providers, update_provider, delete_provider
from app.schemas.provider import ProviderCreate, ProviderUpdate, ProviderResponse
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/providers", tags=["Providers"])


def _fmt(doc: dict) -> dict:
    if not doc:
        return doc
    doc.setdefault("similarity_score", 0.0)
    doc.setdefault("source", "manual")
    doc.setdefault("category", "pending_review")
    doc.setdefault("discovery_status", "discovered")
    doc.setdefault("verification_status", "unverified")
    for f in ("created_at", "updated_at", "last_crawled_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc


@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_providers_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    verification_status: Optional[str] = None,
    discovery_status: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_providers(db, skip, limit, search, category, country, verification_status, discovery_status)
    return paginate([_fmt(i) for i in items], total, page, limit)


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_provider_route(
    data: ProviderCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await create_provider(db, data.model_dump(), str(user.get("_id", "")))
    return _fmt(doc)


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider_route(
    provider_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_provider(db, provider_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _fmt(doc)


@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider_route(
    provider_id: str,
    data: ProviderUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await update_provider(db, provider_id, update_data)
    if not doc:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _fmt(doc)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_route(
    provider_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    deleted = await delete_provider(db, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
