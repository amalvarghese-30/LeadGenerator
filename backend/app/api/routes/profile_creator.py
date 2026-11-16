"""
Auto Profile Creator API Router.
- Discover public profiles for individuals.
- Review candidates with confidence & evidence attribution.
- Save confirmed profile to Contacts CRM.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.services.profile_creator_service import AutoProfileCreatorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile-creator", tags=["Auto Profile Creator"])


class ProfileDiscoverRequest(BaseModel):
    full_name: str
    company: Optional[str] = None
    designation: Optional[str] = None
    location: Optional[str] = None


class ProfileSaveRequest(BaseModel):
    candidate_data: Dict[str, Any]
    create_lead: bool = True


@router.post("/discover")
async def discover_profile_endpoint(
    data: ProfileDiscoverRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = AutoProfileCreatorService(db)
    return await service.discover_profile(
        full_name=data.full_name,
        company=data.company,
        designation=data.designation,
        location=data.location,
        user_id=str(user.get("_id", "")),
    )


@router.post("/save")
async def save_profile_endpoint(
    data: ProfileSaveRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = AutoProfileCreatorService(db)
    return await service.save_profile_to_crm(
        candidate_data=data.candidate_data,
        create_lead=data.create_lead,
        user_id=str(user.get("_id", "")),
    )


@router.get("/candidates")
async def list_recent_candidates_endpoint(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = AutoProfileCreatorService(db)
    return await service.list_recent_candidates(limit=limit)
