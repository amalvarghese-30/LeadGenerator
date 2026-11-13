from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase


async def get_dashboard_stats(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Aggregate top-level stats for the dashboard."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    total_providers = await db.providers.count_documents({})
    verified_providers = await db.providers.count_documents({"verification_status": "verified"})
    total_leads = await db.leads.count_documents({})
    verified_leads = await db.leads.count_documents({"crm_stage": {"$in": ["verified", "qualified", "ready_for_outreach_review"]}})
    outreach_ready = await db.leads.count_documents({"outreach_eligible": True})
    follow_ups_due = await db.leads.count_documents({
        "next_follow_up": {"$lte": now.isoformat()},
        "crm_stage": {"$nin": ["converted", "closed", "disqualified", "do_not_contact"]},
    })
    new_leads_7d = await db.leads.count_documents({"created_at": {"$gte": week_ago}})
    total_contacts = await db.contacts.count_documents({})
    total_companies = await db.companies.count_documents({})
    pending_jobs = await db.crawl_jobs.count_documents({"status": {"$in": ["pending", "running"]}})

    return {
        "total_providers": total_providers,
        "verified_providers": verified_providers,
        "total_leads": total_leads,
        "verified_leads": verified_leads,
        "outreach_ready_leads": outreach_ready,
        "follow_ups_due": follow_ups_due,
        "new_leads_7d": new_leads_7d,
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "pending_crawl_jobs": pending_jobs,
        "generated_at": now.isoformat(),
    }


async def get_provider_report(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Provider breakdown by category and country."""
    cat_pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    cat_results = await db.providers.aggregate(cat_pipeline).to_list(length=50)

    country_pipeline = [
        {"$match": {"country": {"$ne": None}}},
        {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    country_results = await db.providers.aggregate(country_pipeline).to_list(length=20)

    return {
        "by_category": {r["_id"]: r["count"] for r in cat_results},
        "by_country": {r["_id"]: r["count"] for r in country_results},
    }


async def get_leads_report(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Lead breakdown by stage, priority, source."""
    stage_pipeline = [
        {"$group": {"_id": "$crm_stage", "count": {"$sum": 1}, "avg_score": {"$avg": "$lead_score"}}},
        {"$sort": {"_id": 1}},
    ]
    stage_results = await db.leads.aggregate(stage_pipeline).to_list(length=50)

    priority_pipeline = [
        {"$group": {"_id": "$lead_priority", "count": {"$sum": 1}}},
    ]
    priority_results = await db.leads.aggregate(priority_pipeline).to_list(length=10)

    source_pipeline = [
        {"$group": {"_id": "$lead_source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    source_results = await db.leads.aggregate(source_pipeline).to_list(length=20)

    return {
        "by_stage": {r["_id"]: {"count": r["count"], "avg_score": round(r.get("avg_score") or 0, 1)} for r in stage_results},
        "by_priority": {r["_id"]: r["count"] for r in priority_results},
        "by_source": {r["_id"]: r["count"] for r in source_results},
    }


async def get_pipeline_report(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Full pipeline stats."""
    from app.crm.pipeline_service import get_pipeline_stats, get_conversion_funnel
    pipeline_stats = await get_pipeline_stats(db)
    funnel = await get_conversion_funnel(db)
    return {"pipeline": pipeline_stats, "funnel": funnel}
