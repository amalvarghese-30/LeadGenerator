import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.database.connection import get_database, connect_to_mongo, close_mongo_connection

async def get_details():
    await connect_to_mongo()
    db = get_database()
    
    print('=== FAILED SCANS (11) ===')
    cursor = db.crawl_jobs.find({'status': 'failed'})
    async for j in cursor:
        url = j.get('starting_url')
        errs = j.get('errors', [])
        msg = errs[0] if errs else 'Crawl failed / timeout'
        if isinstance(msg, dict):
            msg = msg.get('message') or str(msg)
        print(f"FAILED: {url} -> {msg}")

    print('\n=== CURRENTLY RUNNING (1) ===')
    async for j in db.crawl_jobs.find({'status': 'running'}):
        print(f"RUNNING: {j.get('starting_url')} | Progress: {j.get('progress_pct', 0)}% | Stage: {j.get('current_stage')}")

    print('\n=== ALL REMAINING PENDING WEBSITES ===')
    pending = []
    async for j in db.crawl_jobs.find({'status': 'pending'}).sort('created_at', 1):
        pending.append(j.get('starting_url'))
    
    # Also check unqueued providers
    async for p in db.providers.find({'crawl_job_id': {'$exists': False}}):
        if p.get('website') and p.get('website') not in pending:
            pending.append(p.get('website'))
            
    print(f"Total Remaining to Scan: {len(pending)}")
    for idx, u in enumerate(pending, 1):
        print(f"{idx}. {u}")
        
    await close_mongo_connection()

if __name__ == '__main__':
    asyncio.run(get_details())
