import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.database.connection import get_database, connect_to_mongo, close_mongo_connection

async def inspect():
    await connect_to_mongo()
    db = get_database()
    
    # Jobs summary
    pipeline_jobs = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    job_counts = await db.crawl_jobs.aggregate(pipeline_jobs).to_list(100)
    print("=== CRAWL JOBS SUMMARY ===")
    for item in job_counts:
        print(f"  Status '{item['_id']}': {item['count']}")
        
    total_jobs = await db.crawl_jobs.count_documents({})
    completed_jobs = await db.crawl_jobs.count_documents({"status": "completed"})
    failed_jobs = await db.crawl_jobs.count_documents({"status": "failed"})
    running_jobs = await db.crawl_jobs.count_documents({"status": "running"})
    pending_jobs = await db.crawl_jobs.count_documents({"status": "pending"})
    
    print(f"\nTotal Jobs: {total_jobs} | Completed: {completed_jobs} | Failed: {failed_jobs} | Running: {running_jobs} | Pending: {pending_jobs}")
    
    # Providers summary
    total_providers = await db.providers.count_documents({})
    pipeline_providers = [
        {"$group": {"_id": "$discovery_status", "count": {"$sum": 1}}}
    ]
    provider_counts = await db.providers.aggregate(pipeline_providers).to_list(100)
    print("\n=== PROVIDERS SUMMARY ===")
    print(f"Total Providers: {total_providers}")
    for item in provider_counts:
        print(f"  Discovery Status '{item['_id']}': {item['count']}")
        
    # CRM Data
    total_companies = await db.companies.count_documents({})
    total_contacts = await db.contacts.count_documents({})
    total_leads = await db.leads.count_documents({})
    print("\n=== CRM DISCOVERY SUMMARY ===")
    print(f"Companies: {total_companies} | Contacts: {total_contacts} | Leads: {total_leads}")

    # Detailed lists
    print("\n=== COMPLETED SCANS ===")
    cursor_completed = db.crawl_jobs.find({"status": "completed"}).sort("updated_at", -1)
    completed_list = []
    async for j in cursor_completed:
        prov = await db.providers.find_one({"_id": j.get("provider_id")}) if j.get("provider_id") else None
        name = prov.get("name") if prov else j.get("starting_url", "")
        completed_list.append({
            "url": j.get("starting_url"),
            "name": name,
            "pages": j.get("pages_crawled", 0),
            "contacts": j.get("contacts_created", 0),
            "companies": j.get("companies_created", 0),
        })
    print(f"Count: {len(completed_list)}")
    for item in completed_list:
        print(f"  [OK] {item['name']} ({item['url']}) - Pages: {item['pages']}, Companies: {item['companies']}, Contacts: {item['contacts']}")

    print("\n=== FAILED SCANS ===")
    cursor_failed = db.crawl_jobs.find({"status": "failed"}).sort("updated_at", -1)
    failed_list = []
    async for j in cursor_failed:
        prov = await db.providers.find_one({"_id": j.get("provider_id")}) if j.get("provider_id") else None
        name = prov.get("name") if prov else j.get("starting_url", "")
        errs = j.get("errors", [])
        err_msg = errs[0].get("message") if errs and isinstance(errs[0], dict) else (errs[0] if errs else "Unknown error")
        failed_list.append({
            "url": j.get("starting_url"),
            "name": name,
            "error": err_msg,
        })
    print(f"Count: {len(failed_list)}")
    for item in failed_list:
        print(f"  [FAILED] {item['name']} ({item['url']}) - Error: {item['error']}")

    print("\n=== RUNNING SCANS ===")
    cursor_running = db.crawl_jobs.find({"status": "running"})
    running_list = []
    async for j in cursor_running:
        prov = await db.providers.find_one({"_id": j.get("provider_id")}) if j.get("provider_id") else None
        name = prov.get("name") if prov else j.get("starting_url", "")
        running_list.append({
            "url": j.get("starting_url"),
            "name": name,
            "progress": j.get("progress_pct", 0),
            "stage": j.get("current_stage", ""),
        })
    print(f"Count: {len(running_list)}")
    for item in running_list:
        print(f"  [RUNNING] {item['name']} ({item['url']}) - Stage: {item['stage']} ({item['progress']}%)")

    print("\n=== PENDING / QUEUED SCANS ===")
    cursor_pending = db.crawl_jobs.find({"status": "pending"})
    pending_list = []
    async for j in cursor_pending:
        prov = await db.providers.find_one({"_id": j.get("provider_id")}) if j.get("provider_id") else None
        name = prov.get("name") if prov else j.get("starting_url", "")
        pending_list.append({
            "url": j.get("starting_url"),
            "name": name,
        })
    print(f"Count: {len(pending_list)}")
    for item in pending_list:
        print(f"  [PENDING] {item['name']} ({item['url']})")

    # Check unqueued providers
    pipeline_unqueued = [
        {"$match": {"crawl_job_id": {"$exists": False}}},
    ]
    unqueued = await db.providers.find({"crawl_job_id": {"$exists": False}}).to_list(100)
    if unqueued:
        print(f"\n=== PROVIDERS NEVER QUEUED FOR CRAWL ({len(unqueued)}) ===")
        for p in unqueued:
            print(f"  [NEVER QUEUED] {p.get('name')} ({p.get('website')})")

    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(inspect())
