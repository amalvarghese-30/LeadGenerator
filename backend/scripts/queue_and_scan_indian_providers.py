import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import get_database, connect_to_mongo, close_mongo_connection
from app.utils.url_utils import extract_domain, normalize_url
from app.workers.job_processor import JobProcessor

INDIAN_PROVIDERS = [
    "https://thewiseidiot.in/",
    "https://thegotoguy.co/",
    "https://brandemic.in/",
    "https://brandnine.in/",
    "https://sociolabs.in/",
    "https://tprindia.in/",
    "https://romitpr.com/",
    "https://studiosorted.com/",
    "https://townmedialabs.com/",
    "https://30thfeb.com/",
]

async def queue_and_run():
    await connect_to_mongo()
    db = get_database()
    
    print(f"\n========================================================")
    print(f"  ADDING & QUEUEING 10 NEW INDIAN PROVIDERS")
    print(f"========================================================\n")
    
    jobs = []
    
    for url in INDIAN_PROVIDERS:
        norm_url = normalize_url(url)
        domain = extract_domain(norm_url)
        name = domain.replace("www.", "")
        
        provider_doc = await db.providers.find_one({"$or": [{"website": norm_url}, {"domain": domain}]})
        if not provider_doc:
            provider_doc = {
                "name": name,
                "website": norm_url,
                "domain": domain,
                "category": "direct_competitor",
                "country": "India",
                "discovery_status": "researching",
                "verification_status": "unverified",
                "source": "indian_agency_discovery",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            res = await db.providers.insert_one(provider_doc)
            provider_doc["_id"] = res.inserted_id
            print(f"[CREATED] Provider: {name} (India)")
        else:
            print(f"[EXISTING] Provider: {name}")
            
        provider_id = str(provider_doc["_id"])
        
        # Check job
        job_doc = await db.crawl_jobs.find_one({
            "provider_id": provider_id,
            "status": {"$in": ["pending", "running"]}
        })
        if not job_doc:
            now = datetime.utcnow()
            job_doc = {
                "provider_id": provider_id,
                "starting_url": norm_url,
                "job_type": "full_research",
                "status": "pending",
                "current_stage": "queued",
                "progress_pct": 0,
                "pages_discovered": 0,
                "pages_attempted": 0,
                "pages_crawled": 0,
                "pages_failed": 0,
                "pages_skipped": 0,
                "references_found": 0,
                "contacts_created": 0,
                "companies_created": 0,
                "leads_created": 0,
                "errors": [],
                "warnings": [],
                "created_by": "indian_batch_scanner",
                "created_at": now,
                "updated_at": now,
            }
            j_res = await db.crawl_jobs.insert_one(job_doc)
            job_doc["_id"] = j_res.inserted_id
            await db.providers.update_one(
                {"_id": provider_doc["_id"]},
                {"$set": {"discovery_status": "researching", "crawl_job_id": str(j_res.inserted_id)}}
            )
            print(f"  -> [QUEUED] Job: {j_res.inserted_id}")
            
        jobs.append(job_doc)
        
    print(f"\n========================================================")
    print(f"  EXECUTING SCANS ON {len(jobs)} INDIAN PROVIDERS")
    print(f"========================================================\n")
    
    processor = JobProcessor()
    
    for idx, job in enumerate(jobs, 1):
        job_id = str(job["_id"])
        url = job.get("starting_url")
        print(f"\n>>> [{idx}/{len(jobs)}] SCANNING: {url} (Job: {job_id})")
        
        await db.crawl_jobs.update_one(
            {"_id": job["_id"]},
            {"$set": {
                "status": "running",
                "current_stage": "discovering",
                "started_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        try:
            await processor.process_job(job, db)
            print(f">>> [{idx}/{len(jobs)}] COMPLETED: {url}")
        except Exception as e:
            print(f">>> [{idx}/{len(jobs)}] FAILED: {url} -> {e}")
            await db.crawl_jobs.update_one(
                {"_id": job["_id"]},
                {"$set": {
                    "status": "failed",
                    "current_stage": "failed",
                    "updated_at": datetime.utcnow(),
                    "errors": [{"stage": "scan", "message": str(e), "timestamp": datetime.utcnow().isoformat()}]
                }}
            )
            
    print("\nAll 10 Indian agency scans completed successfully!")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(queue_and_run())
