"""
Competitor Intelligence API Router.
- Full CRUD for Competitors
- Competitor discovery
- Run Competitor research
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.services.competitor_service import CompetitorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/competitors", tags=["Competitor Intelligence"])


class CompetitorCreateRequest(BaseModel):
    name: str
    website: Optional[str] = None
    business_category: Optional[str] = "Agency / Marketing"
    services: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CompetitorUpdateRequest(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    business_category: Optional[str] = None
    services: Optional[List[str]] = None
    notes: Optional[str] = None


class CompetitorDiscoverRequest(BaseModel):
    seed_terms: str
    category: Optional[str] = None
    region: Optional[str] = None
    max_results: int = Field(15, ge=1, le=50)


@router.get("")
async def list_competitors_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    return await service.list_competitors(skip=skip, limit=limit, category=category, search=search)


@router.get("/{competitor_id}")
async def get_competitor_endpoint(
    competitor_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    doc = await service.get_competitor(competitor_id)
    if not doc:
        raise HTTPException(404, "Competitor not found")
    return doc


@router.post("")
async def create_competitor_endpoint(
    data: CompetitorCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    return await service.create_competitor(data.model_dump())


@router.put("/{competitor_id}")
async def update_competitor_endpoint(
    competitor_id: str,
    data: CompetitorUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await service.update_competitor(competitor_id, update_data)
    if not doc:
        raise HTTPException(404, "Competitor not found")
    return doc


@router.delete("/{competitor_id}")
async def delete_competitor_endpoint(
    competitor_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    deleted = await service.delete_competitor(competitor_id)
    if not deleted:
        raise HTTPException(404, "Competitor not found")
    return {"message": "Competitor deleted successfully"}


@router.post("/discover")
async def discover_competitors_endpoint(
    data: CompetitorDiscoverRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    return await service.discover_competitors(
        seed_terms=data.seed_terms,
        category=data.category,
        region=data.region,
        max_results=data.max_results,
    )


@router.post("/{competitor_id}/research")
async def run_competitor_research_endpoint(
    competitor_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = CompetitorService(db)
    res = await service.run_competitor_research(competitor_id)
    if not res:
        raise HTTPException(404, "Competitor not found")
    return res
