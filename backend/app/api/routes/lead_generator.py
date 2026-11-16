"""
Lead Generator API Router.
- Company Search endpoint
- Individual Search endpoint
- Entity Classification endpoint
- Search History endpoint
- Save Search Result to CRM endpoint
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.dependencies import get_db, get_current_user
from app.services.lead_generator_service import LeadGeneratorService, EntityClassifier
from app.crm.company_service import CompanyService
from app.crm.contact_service import ContactService
from app.crm.lead_service import LeadService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lead-generator", tags=["Lead Generator"])


class CompanySearchRequest(BaseModel):
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    additional_terms: Optional[str] = None
    max_results: int = Field(15, ge=1, le=50)


class IndividualSearchRequest(BaseModel):
    full_name: str
    company: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    max_results: int = Field(15, ge=1, le=50)


class ClassifyRequest(BaseModel):
    title: str
    snippet: str
    url: str


class SaveToCrmRequest(BaseModel):
    entity_type: str  # "company", "individual", "organisation"
    name: str
    website: Optional[str] = None
    domain: Optional[str] = None
    title: Optional[str] = None
    company_name: Optional[str] = None
    snippet: Optional[str] = None
    social_platform: Optional[str] = None
    url: Optional[str] = None
    create_lead: bool = True


@router.post("/company")
async def company_search_endpoint(
    data: CompanySearchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = LeadGeneratorService(db)
    return await service.search_company(
        company_name=data.company_name,
        website=data.website,
        industry=data.industry,
        country=data.country,
        additional_terms=data.additional_terms,
        max_results=data.max_results,
        user_id=str(user.get("_id", "")),
    )


@router.post("/individual")
async def individual_search_endpoint(
    data: IndividualSearchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = LeadGeneratorService(db)
    return await service.search_individual(
        full_name=data.full_name,
        company=data.company,
        job_title=data.job_title,
        location=data.location,
        max_results=data.max_results,
        user_id=str(user.get("_id", "")),
    )


@router.post("/classify")
async def classify_entity_endpoint(
    data: ClassifyRequest,
    _user: dict = Depends(get_current_user),
):
    return EntityClassifier.classify(data.title, data.snippet, data.url)


@router.get("/history")
async def get_search_history_endpoint(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = LeadGeneratorService(db)
    return await service.get_search_history(limit=limit, user_id=str(user.get("_id", "")))


@router.post("/save")
async def save_search_result_to_crm(
    data: SaveToCrmRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Directly converts a search result candidate into CRM records.
    """
    company_service = CompanyService(db)
    contact_service = ContactService(db)
    lead_service = LeadService(db)

    company_id = None
    contact_id = None
    lead_id = None

    if data.entity_type in ("company", "organisation") or not data.company_name:
        comp_res = await company_service.create({
            "name": data.company_name or data.name,
            "website": data.website or (data.url if "linkedin.com" not in (data.url or "") else None),
            "notes": data.snippet,
        })
        company_id = comp_res.get("id")

    if data.entity_type == "individual" or data.title:
        prof_urls = {}
        if data.social_platform and data.url:
            prof_urls[data.social_platform] = data.url

        contact_doc, _ = await contact_service.create({
            "full_name": data.name,
            "designation": data.title or "Executive",
            "company_id": company_id,
            "company_name": data.company_name,
            "professional_urls": prof_urls,
            "linkedin_url": prof_urls.get("linkedin"),
            "notes": data.snippet,
            "contact_verification_status": "discovered",
        })
        contact_id = contact_doc.get("id")

    if data.create_lead and contact_id:
        lead_res = await lead_service.create(
            contact_id=contact_id,
            company_id=company_id,
            lead_source="lead_generator",
            initial_stage="discovered",
            user_id=str(user.get("_id", "")),
        )
        lead_id = lead_res.get("id")

    return {
        "status": "success",
        "company_id": company_id,
        "contact_id": contact_id,
        "lead_id": lead_id,
    }
