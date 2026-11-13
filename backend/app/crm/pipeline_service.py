from datetime import datetime, timezone
from typing import Any, Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase


async def get_pipeline_stats(db: AsyncIOMotorDatabase) -> Dict:
    """Return lead counts per CRM stage."""
    pipeline = [
        {"$group": {"_id": "$crm_stage", "count": {"$sum": 1}, "avg_score": {"$avg": "$lead_score"}}},
        {"$sort": {"_id": 1}},
    ]
    cursor = db.leads.aggregate(pipeline)
    results = await cursor.to_list(length=100)
    stages = {r["_id"]: {"count": r["count"], "avg_score": round(r.get("avg_score", 0), 1)} for r in results}
    return stages


async def get_kanban_data(db: AsyncIOMotorDatabase, limit_per_stage: int = 20) -> Dict[str, List[Dict]]:
    """Return leads grouped by CRM stage for kanban view."""
    from app.models.lead import CRM_STAGES
    kanban: Dict[str, List[Dict]] = {stage: [] for stage in CRM_STAGES}

    for stage in CRM_STAGES:
        cursor = db.leads.find({"crm_stage": stage}).sort("lead_score", -1).limit(limit_per_stage)
        docs = await cursor.to_list(length=limit_per_stage)
        for doc in docs:
            if "_id" in doc:
                doc["id"] = str(doc.pop("_id"))
        kanban[stage] = docs
    return kanban


async def get_conversion_funnel(db: AsyncIOMotorDatabase) -> List[Dict]:
    """Return stage-by-stage conversion data."""
    from app.models.lead import CRM_STAGES
    result = []
    for stage in CRM_STAGES:
        count = await db.leads.count_documents({"crm_stage": stage})
        result.append({"stage": stage, "count": count})
    return result


class PipelineService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_pipeline_stats(self) -> Dict:
        return await get_pipeline_stats(self.db)

    async def get_kanban_data(self, limit_per_stage: int = 20) -> Dict[str, List[Dict]]:
        return await get_kanban_data(self.db, limit_per_stage)

    async def get_conversion_funnel(self) -> List[Dict]:
        return await get_conversion_funnel(self.db)

