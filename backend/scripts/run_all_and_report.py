import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from bson import ObjectId

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import get_database, connect_to_mongo, close_mongo_connection
from app.workers.job_processor import JobProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (batch-runner) %(message)s",
)
logger = logging.getLogger("batch_runner")

TARGET_URLS = [
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

async def run_batch():
    await connect_to_mongo()
    db = get_database()
    
    # 1. Reset any stalled 'running' jobs from our target list back to 'pending'
    for url in TARGET_URLS:
        norm = url.rstrip("/")
        await db.crawl_jobs.update_many(
            {"starting_url": {"$regex": f"^{norm}"}, "status": "running"},
            {"$set": {"status": "pending", "current_stage": "queued", "progress_pct": 0}}
        )
    
    # 2. Get all jobs for target URLs
    jobs_to_process = []
    for url in TARGET_URLS:
        norm = url.rstrip("/")
        job = await db.crawl_jobs.find_one({
            "starting_url": {"$regex": f"^{norm}"},
            "status": "pending"
        })
        if job:
            jobs_to_process.append(job)
            
    print(f"\n========================================================")
    print(f"  FOUND {len(jobs_to_process)} TARGET JOBS TO SCAN")
    print(f"========================================================\n")
    
    processor = JobProcessor()
    
    for idx, job in enumerate(jobs_to_process, 1):
        job_id = str(job["_id"])
        url = job.get("starting_url")
        print(f"\n>>> [{idx}/{len(jobs_to_process)}] STARTING SCAN: {url} (Job: {job_id})")
        
        # Mark running
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
            # Process job end-to-end
            await processor.process_job(job, db)
            print(f">>> [{idx}/{len(jobs_to_process)}] FINISHED: {url}")
        except Exception as e:
            logger.exception("Failed processing job %s for %s", job_id, url)
            await db.crawl_jobs.update_one(
                {"_id": job["_id"]},
                {"$set": {
                    "status": "failed",
                    "current_stage": "failed",
                    "updated_at": datetime.utcnow(),
                    "errors": [{"stage": "batch_runner", "message": str(e), "timestamp": datetime.utcnow().isoformat()}]
                }}
            )
            print(f">>> [{idx}/{len(jobs_to_process)}] ERROR: {url} -> {e}")
            
    print(f"\n========================================================")
    print(f"  ALL 15 SCANS PROCESSED - GENERATING RESEARCH REPORT")
    print(f"========================================================\n")
    
    # Generate aggregate report
    report_lines = []
    report_lines.append("# LeadIntel CRM — Multi-Provider Research & Enrichment Report")
    report_lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report_lines.append(f"**Target Providers Scanned:** {len(TARGET_URLS)}\n")
    report_lines.append("## 1. Provider Scans Executive Summary\n")
    report_lines.append("| Provider Domain | Scan Status | Discovered URLs | Extracted References | Contacts Created | Companies Created |")
    report_lines.append("|---|---|---|---|---|---|")
    
    provider_ids = []
    for url in TARGET_URLS:
        norm = url.rstrip("/")
        job = await db.crawl_jobs.find_one({"starting_url": {"$regex": f"^{norm}"}}, sort=[("created_at", -1)])
        if job:
            p_id = job.get("provider_id")
            if p_id:
                provider_ids.append(p_id)
            domain = url.replace("https://", "").replace("http://", "").strip("/")
            status = job.get("status", "unknown")
            disc = job.get("pages_discovered", 0)
            refs = job.get("references_found", 0)
            cont = job.get("contacts_created", 0)
            comp = job.get("companies_created", 0)
            report_lines.append(f"| `{domain}` | **{status}** | {disc} | {refs} | {cont} | {comp} |")
            
    report_lines.append("\n---\n")
    report_lines.append("## 2. Identified Client Contacts & Public Business Enrichment\n")
    
    contacts = await db.contacts.find({}).sort("created_at", -1).to_list(500)
    
    if not contacts:
        report_lines.append("*No contacts created across the scans.*")
    else:
        report_lines.append(f"Total Contacts Identified in CRM: **{len(contacts)}**\n")
        report_lines.append("| Contact Name | Designation | Company | Direct Email | Direct Phone | Company Channels | LinkedIn | Enrichment Status |")
        report_lines.append("|---|---|---|---|---|---|---|---|")
        
        for c in contacts:
            name = c.get("full_name") or "Unnamed"
            desig = c.get("designation") or "Executive"
            comp = c.get("company_name") or "—"
            
            # Direct channels
            channels = c.get("contact_channels") or []
            direct_emails = [ch.get("value") for ch in channels if ch.get("type") == "email" and "direct" in ch.get("scope", "")]
            direct_phones = [ch.get("value") for ch in channels if ch.get("type") == "phone" and "direct" in ch.get("scope", "")]
            company_chs = [ch.get("value") for ch in channels if "company" in ch.get("scope", "")]
            
            email_val = direct_emails[0] if direct_emails else c.get("email") or "Not publicly found"
            phone_val = direct_phones[0] if direct_phones else c.get("phone") or "Not found"
            comp_ch_val = company_chs[0] if company_chs else "None"
            li = c.get("linkedin_url") or "—"
            if li and li.startswith("http"):
                li = f"[Profile]({li})"
            en_status = c.get("enrichment_status") or "not_started"
            
            report_lines.append(f"| **{name}** | {desig} | {comp} | `{email_val}` | `{phone_val}` | `{comp_ch_val}` | {li} | `{en_status}` |")
            
    report_lines.append("\n---\n")
    report_lines.append("## 3. Discovered Client Companies\n")
    companies = await db.companies.find({}).sort("created_at", -1).to_list(500)
    report_lines.append(f"Total Companies Identified: **{len(companies)}**\n")
    report_lines.append("| Company Name | Website | Industry | Country | Phone | Email |")
    report_lines.append("|---|---|---|---|---|---|")
    for comp in companies:
        cname = comp.get("name", "—")
        web = comp.get("website", "—")
        ind = comp.get("industry", "—")
        cntry = comp.get("country", "—")
        ph = comp.get("phone", "—")
        em = comp.get("email", "—")
        report_lines.append(f"| **{cname}** | {web} | {ind} | {cntry} | `{ph}` | `{em}` |")

    report_content = "\n".join(report_lines)
    
    # Save to file
    out_dir = r"C:\Users\Amal Varghese\.gemini\antigravity\brain\41d1ec5c-bc62-4cb5-baf5-9b91afe7599e"
    out_path = os.path.join(out_dir, "15_providers_final_research_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\nReport successfully saved to {out_path}!")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(run_batch())
