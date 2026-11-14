from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.services.export_service import (
    export_leads_to_csv,
    export_leads_to_excel,
    export_providers_to_csv,
    export_contacts_to_csv,
    export_companies_to_csv,
)

router = APIRouter(prefix="/export", tags=["Exports"])

@router.get("/leads")
async def export_leads_route(
    format: str = Query("csv", pattern="^(csv|excel)$"),
    crm_stage: Optional[str] = None,
    lead_priority: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    filters = {}
    if crm_stage:
        filters["crm_stage"] = crm_stage
    if lead_priority:
        filters["lead_priority"] = lead_priority

    if format == "excel":
        content = await export_leads_to_excel(db, filters)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "leads_export.xlsx"
    else:
        content = await export_leads_to_csv(db, filters)
        media_type = "text/csv"
        filename = "leads_export.csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/providers")
async def export_providers_route(
    category: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    filters = {}
    if category:
        filters["category"] = category
    content = await export_providers_to_csv(db, filters)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=providers_export.csv"}
    )

@router.get("/contacts")
async def export_contacts_route(
    verification_status: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    filters = {}
    if verification_status:
        filters["contact_verification_status"] = verification_status
    content = await export_contacts_to_csv(db, filters)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts_export.csv"}
    )

@router.get("/companies")
async def export_companies_route(
    industry: Optional[str] = None,
    country: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    filters = {}
    if industry:
        filters["industry"] = industry
    if country:
        filters["country"] = country
    content = await export_companies_to_csv(db, filters)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=companies_export.csv"}
    )
