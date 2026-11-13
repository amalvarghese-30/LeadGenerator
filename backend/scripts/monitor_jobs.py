import asyncio
from app.database.connection import get_database, connect_to_mongo, close_mongo_connection

async def monitor():
    await connect_to_mongo()
    db = get_database()
    jobs = await db.crawl_jobs.find({}).sort("created_at", 1).to_list(100)
    print("=" * 115)
    print(f"{'URL':<42} {'Status':<16} {'Stage':<14} {'Pct':<6} {'Refs':<6} {'Contacts':<10} {'Companies':<10}")
    print("=" * 115)
    
    pending_count = 0
    running_count = 0
    completed_count = 0
    failed_count = 0
    
    for j in jobs:
        url = str(j.get("starting_url", ""))[:40]
        status = str(j.get("status", ""))
        stage = str(j.get("current_stage", ""))
        pct = f"{j.get('progress_pct', 0)}%"
        refs = j.get("references_found", 0)
        contacts = j.get("contacts_created", 0)
        comps = j.get("companies_created", 0)
        
        if status == "pending":
            pending_count += 1
        elif status == "running":
            running_count += 1
        elif "completed" in status:
            completed_count += 1
        else:
            failed_count += 1
            
        print(f"{url:<42} {status:<16} {stage:<14} {pct:<6} {refs:<6} {contacts:<10} {comps:<10}")
        
    print("=" * 115)
    print(f"Summary: {completed_count} Completed | {running_count} Running | {pending_count} Pending | {failed_count} Failed")
    
    # Also count CRM totals
    total_contacts = await db.contacts.count_documents({})
    total_companies = await db.companies.count_documents({})
    total_leads = await db.leads.count_documents({})
    total_refs = await db.provider_client_references.count_documents({})
    print(f"CRM Totals: {total_contacts} Contacts | {total_companies} Companies | {total_leads} Leads | {total_refs} References")
    print("=" * 115)
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(monitor())
