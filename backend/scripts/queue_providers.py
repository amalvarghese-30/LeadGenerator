import asyncio
from datetime import datetime, timezone
from bson import ObjectId
from app.database.connection import get_database, connect_to_mongo, close_mongo_connection
from app.utils.url_utils import extract_domain, normalize_url
from app.crm.provider_service import create_provider

URLS = [
    "https://www.thepeoplecompany.me/",
    "https://boldface.online/",
    "https://fablesquare.com/",
    "https://www.scribblersindia.com/",
    "https://www.theinfluenceforge.com/",
    "https://i-midastouch.com/",
    "https://www.bharatcxo.com/",
    "https://ohhmybrand.com/",
    "https://postlitmedia.com/",
    "https://www.reputationdefender.com/",
    "https://brandyourself.com/",
    "https://www.reputationmanagement.co/",
    "https://www.reputationx.com/",
    "https://www.instantpress.co/",
    "https://kalicube.com/",
]

async def enqueue_all():
    await connect_to_mongo()
    db = get_database()
    
    print(f"Adding and queueing {len(URLS)} providers for scan...")
    
    queued_jobs = []
    
    for url in URLS:
        norm_url = normalize_url(url)
        domain = extract_domain(norm_url)
        name = domain.replace("www.", "")
        
        # 1. Create or get provider
        provider_doc = await db.providers.find_one({"$or": [{"website": norm_url}, {"domain": domain}]})
        if not provider_doc:
            provider_doc = {
                "name": name,
                "website": norm_url,
                "domain": domain,
                "category": "direct_competitor",
                "discovery_status": "researching",
                "verification_status": "unverified",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            res = await db.providers.insert_one(provider_doc)
            provider_doc["_id"] = res.inserted_id
            print(f"[CREATED] Provider: {name} ({domain})")
        else:
            print(f"[EXISTING] Provider: {name} ({domain})")
            
        provider_id = str(provider_doc["_id"])
        
        # 2. Check if active or pending job exists
        active_job = await db.crawl_jobs.find_one({
            "provider_id": provider_id,
            "status": {"$in": ["pending", "running"]}
        })
        
        if active_job:
            print(f"  -> Job already {active_job.get('status')}: {active_job.get('_id')}")
            queued_jobs.append((name, str(active_job["_id"]), active_job.get("status")))
            continue
            
        # 3. Create full_research crawl job
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
            "created_by": "bulk_scan_admin",
            "created_at": now,
            "updated_at": now,
        }
        j_res = await db.crawl_jobs.insert_one(job_doc)
        job_id = str(j_res.inserted_id)
        
        await db.providers.update_one(
            {"_id": provider_doc["_id"]},
            {"$set": {"discovery_status": "researching", "crawl_job_id": job_id, "updated_at": datetime.now(timezone.utc)}}
        )
        print(f"  -> [QUEUED] Job: {job_id}")
        queued_jobs.append((name, job_id, "pending"))
        
    print("\n--- Summary ---")
    for name, jid, status in queued_jobs:
        print(f"Provider: {name:<30} | Job: {jid} | Status: {status}")
        
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(enqueue_all())
