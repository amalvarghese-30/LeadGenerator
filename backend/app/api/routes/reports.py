from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.services.report_service import (
    get_dashboard_stats, get_provider_report, get_leads_report, get_pipeline_report,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard")
async def dashboard_stats_route(db: AsyncIOMotorDatabase = Depends(get_db),
                                _user: dict = Depends(get_current_user)):
    return await get_dashboard_stats(db)


@router.get("/providers")
async def provider_report_route(db: AsyncIOMotorDatabase = Depends(get_db),
                                _user: dict = Depends(get_current_user)):
    return await get_provider_report(db)


@router.get("/leads")
async def leads_report_route(db: AsyncIOMotorDatabase = Depends(get_db),
                             _user: dict = Depends(get_current_user)):
    return await get_leads_report(db)


@router.get("/pipeline")
async def pipeline_report_route(db: AsyncIOMotorDatabase = Depends(get_db),
                                _user: dict = Depends(get_current_user)):
    return await get_pipeline_report(db)


@router.get("/research")
async def research_reports_route(db: AsyncIOMotorDatabase = Depends(get_db),
                                 _user: dict = Depends(get_current_user)):
    cursor = db.research_reports.find({}).sort("generated_at", -1).limit(50)
    docs = await cursor.to_list(50)
    out = []
    for d in docs:
        if "_id" in d:
            d["id"] = str(d.pop("_id"))
        if d.get("generated_at") and hasattr(d["generated_at"], "isoformat"):
            d["generated_at"] = d["generated_at"].isoformat()
        out.append(d)
    return {"reports": out}