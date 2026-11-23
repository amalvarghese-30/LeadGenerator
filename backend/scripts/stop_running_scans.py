import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.database.connection import get_database, connect_to_mongo, close_mongo_connection
from app.config import settings

async def stop_all_running():
    await connect_to_mongo()
    db = get_database()
    
    # 1. Check all running jobs
    running_jobs = await db.crawl_jobs.find({"status": "running"}).to_list(100)
    print(f"Found {len(running_jobs)} currently running crawl job(s).")
    
    now = datetime.now(timezone.utc)
    stopped_urls = []
    
    # Try connecting to Redis if enabled or configured to set cancellation flag
    try:
        if settings.REDIS_ENABLED or settings.REDIS_URL:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            for j in running_jobs:
                jid = str(j["_id"])
                await r.set(f"cancel_job:{jid}", "1", ex=86400)
                await r.publish(f"job_events:{jid}", '{"type": "job_cancelled"}')
            await r.aclose()
            print("Set Redis cancellation flags.")
    except Exception as e:
        print(f"Notice: Redis notification skipped ({e})")
        
    for j in running_jobs:
        jid = j["_id"]
        url = j.get("starting_url", "Unknown URL")
        stopped_urls.append(url)
        
        await db.crawl_jobs.update_one(
            {"_id": jid},
            {
                "$set": {
                    "status": "cancelled",
                    "current_stage": "cancelled",
                    "updated_at": now,
                    "cancelled_at": now,
                },
                "$push": {
                    "warnings": f"Scan cancelled by user at {now.isoformat()}"
                }
            }
        )
        print(f"Cancelled job {jid} for {url}")
        
        # Also update provider status
        if j.get("provider_id"):
            await db.providers.update_one(
                {"_id": j["provider_id"], "discovery_status": "researching"},
                {"$set": {"discovery_status": "cancelled", "updated_at": now}}
            )

    # Verification: check if any job is still running
    remaining_running = await db.crawl_jobs.count_documents({"status": "running"})
    print(f"\nVerification: Remaining running jobs count = {remaining_running}")
    
    await close_mongo_connection()
    return stopped_urls

if __name__ == "__main__":
    asyncio.run(stop_all_running())
