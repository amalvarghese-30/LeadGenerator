"""
Automated scheduler using APScheduler.
Enqueues background jobs for recurring website recrawling, RSS feed checks,
and follow-up task notifications without blocking HTTP handlers.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.connection import get_database

logger = logging.getLogger(__name__)

scheduler: Optional[AsyncIOScheduler] = None

async def check_rss_feeds_job():
    """Periodic job to check registered providers for fresh RSS updates."""
    logger.info("[Scheduler] Checking provider RSS feeds for updates...")
    db = get_database()
    try:
        # Find active providers
        providers = await db.providers.find({"discovery_status": {"$in": ["approved", "researched"]}}).to_list(50)
        from app.discovery.rss import RSSDiscovery
        rss = RSSDiscovery()

        for p in providers:
            site = p.get("website")
            if site:
                feeds = await rss.discover_feeds(site)
                if feeds:
                    logger.debug(f"Found feeds for {p.get('name')}: {feeds}")
    except Exception as e:
        logger.warning(f"Error in RSS schedule check: {e}")

async def recrawl_outdated_providers_job():
    """Enqueue recrawl job for providers not crawled in 14+ days."""
    logger.info("[Scheduler] Evaluating outdated providers for recrawling...")
    db = get_database()
    cutoff = datetime.utcnow() - timedelta(days=14)
    try:
        outdated = await db.providers.find({
            "discovery_status": "researched",
            "last_crawled_at": {"$lt": cutoff}
        }).to_list(10)

        for p in outdated:
            existing = await db.crawl_jobs.find_one({
                "provider_id": str(p["_id"]),
                "status": {"$in": ["pending", "running"]}
            })
            if not existing and p.get("website"):
                await db.crawl_jobs.insert_one({
                    "provider_id": str(p["_id"]),
                    "starting_url": p["website"],
                    "status": "pending",
                    "job_type": "scheduled_recrawl",
                    "created_at": datetime.utcnow()
                })
                logger.info(f"Enqueued scheduled recrawl for {p.get('name')}")
    except Exception as e:
        logger.warning(f"Error checking outdated providers: {e}")

def start_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        # Schedule RSS check every 6 hours
        scheduler.add_job(check_rss_feeds_job, 'interval', hours=6, id='rss_checker')
        # Schedule provider recrawl check daily at midnight
        scheduler.add_job(recrawl_outdated_providers_job, 'cron', hour=0, id='recrawl_checker')
        scheduler.start()
        logger.info("APScheduler initialized and started successfully.")

def shutdown_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down.")
