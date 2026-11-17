import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel, TEXT

logger = logging.getLogger(__name__)


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    logger.info("Creating MongoDB indexes...")

    await db.users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True, name="users_email_unique"),
        IndexModel([("username", ASCENDING)], unique=True, sparse=True, name="users_username_unique"),
        IndexModel([("created_at", DESCENDING)], name="users_created_at"),
        IndexModel([("is_active", ASCENDING)], name="users_is_active"),
    ])

    await db.providers.create_indexes([
        IndexModel([("domain", ASCENDING)], unique=True, sparse=True, name="providers_domain_unique"),
        IndexModel([("name", TEXT), ("description", TEXT), ("services", TEXT)], name="providers_text_search"),
        IndexModel([("category", ASCENDING)], name="providers_category"),
        IndexModel([("discovery_status", ASCENDING)], name="providers_discovery_status"),
        IndexModel([("verification_status", ASCENDING)], name="providers_verification_status"),
        IndexModel([("created_at", DESCENDING)], name="providers_created_at"),
    ])

    await db.companies.create_indexes([
        IndexModel([("dedup_key", ASCENDING)], unique=True, sparse=True, name="companies_dedup_key_unique"),
        IndexModel([("domain", ASCENDING)], sparse=True, name="companies_domain"),
        IndexModel([("name", TEXT)], name="companies_text_search"),
        IndexModel([("industry", ASCENDING)], name="companies_industry"),
        IndexModel([("created_at", DESCENDING)], name="companies_created_at"),
    ])

    await db.contacts.create_indexes([
        IndexModel([("dedup_key", ASCENDING)], unique=True, sparse=True, name="contacts_dedup_key_unique"),
        IndexModel([("company_id", ASCENDING)], name="contacts_company_id"),
        IndexModel([("full_name", TEXT), ("designation", TEXT)], name="contacts_text_search"),
        IndexModel([("contact_verification_status", ASCENDING)], name="contacts_verification_status"),
        IndexModel([("created_at", DESCENDING)], name="contacts_created_at"),
    ])

    await db.leads.create_indexes([
        IndexModel([("contact_id", ASCENDING)], name="leads_contact_id"),
        IndexModel([("company_id", ASCENDING)], name="leads_company_id"),
        IndexModel([("crm_stage", ASCENDING)], name="leads_crm_stage"),
        IndexModel([("lead_score", DESCENDING)], name="leads_lead_score"),
        IndexModel([("created_at", DESCENDING)], name="leads_created_at"),
    ])

    await db.provider_client_references.create_indexes([
        IndexModel([("provider_id", ASCENDING)], name="references_provider_id"),
        IndexModel([("source_url", ASCENDING)], name="references_source_url"),
        IndexModel([("verification_status", ASCENDING)], name="references_verification_status"),
        IndexModel([("created_at", DESCENDING)], name="references_created_at"),
    ])

    await db.crawl_jobs.create_indexes([
        IndexModel([("status", ASCENDING)], name="crawl_jobs_status"),
        IndexModel([("provider_id", ASCENDING)], sparse=True, name="crawl_jobs_provider_id"),
        IndexModel([("lock_key", ASCENDING)], sparse=True, name="crawl_jobs_lock_key"),
        IndexModel([("created_at", DESCENDING)], name="crawl_jobs_created_at"),
    ])

    # --- NEW ---
    await db.crawl_pages.create_indexes([
        IndexModel([("job_id", ASCENDING)], name="crawl_pages_job_id"),
        IndexModel([("provider_id", ASCENDING)], name="crawl_pages_provider_id"),
        IndexModel([("url", ASCENDING)], name="crawl_pages_url"),
        IndexModel([("crawled_at", DESCENDING)], name="crawl_pages_crawled_at"),
    ])

    await db.research_reports.create_indexes([
        IndexModel([("job_id", ASCENDING)], unique=True, name="research_reports_job_id_unique"),
        IndexModel([("provider_id", ASCENDING)], name="research_reports_provider_id"),
        IndexModel([("generated_at", DESCENDING)], name="research_reports_generated_at"),
    ])

    await db.activities.create_indexes([
        IndexModel([("lead_id", ASCENDING)], sparse=True, name="activities_lead_id"),
        IndexModel([("activity_type", ASCENDING)], name="activities_type"),
        IndexModel([("created_at", DESCENDING)], name="activities_created_at"),
    ])

    await db.tasks.create_indexes([
        IndexModel([("status", ASCENDING)], name="tasks_status"),
        IndexModel([("due_date", ASCENDING)], name="tasks_due_date"),
    ])

    await db.job_events.create_indexes([
        IndexModel([("job_id", ASCENDING)], name="job_events_job_id"),
        IndexModel([("event_timestamp", ASCENDING)], name="job_events_timestamp_asc"),
        IndexModel([("stage", ASCENDING)], name="job_events_stage"),
        IndexModel([("severity", ASCENDING)], name="job_events_severity"),
    ])

    await db.competitors.create_indexes([
        IndexModel([("domain", ASCENDING)], sparse=True, name="competitors_domain"),
        IndexModel([("name", TEXT), ("business_category", TEXT)], name="competitors_text_search"),
        IndexModel([("created_at", DESCENDING)], name="competitors_created_at"),
    ])

    await db.rate_limit_metrics.create_indexes([
        IndexModel([("domain", ASCENDING)], name="rate_limits_domain"),
        IndexModel([("timestamp", DESCENDING)], name="rate_limits_timestamp"),
        IndexModel([("is_throttled", ASCENDING)], name="rate_limits_throttled"),
    ])

    await db.rate_limit_request_logs.create_indexes([
        IndexModel([("domain", ASCENDING)], name="rl_request_logs_domain"),
        IndexModel([("timestamp", DESCENDING)], name="rl_request_logs_timestamp"),
        IndexModel([("classification", ASCENDING)], name="rl_request_logs_classification"),
        IndexModel([("status_code", ASCENDING)], name="rl_request_logs_status"),
    ])

    await db.domain_rate_profiles.create_indexes([
        IndexModel([("domain", ASCENDING)], unique=True, name="domain_profiles_domain_unique"),
        IndexModel([("status", ASCENDING)], name="domain_profiles_status"),
        IndexModel([("updated_at", DESCENDING)], name="domain_profiles_updated_at"),
    ])

    await db.rate_limit_events.create_indexes([
        IndexModel([("domain", ASCENDING)], name="rate_limit_events_domain"),
        IndexModel([("timestamp", DESCENDING)], name="rate_limit_events_timestamp"),
        IndexModel([("event_type", ASCENDING)], name="rate_limit_events_type"),
    ])

    await db.api_rate_limit_profiles.create_indexes([
        IndexModel([("provider", ASCENDING)], unique=True, name="api_profiles_provider_unique"),
    ])

    await db.search_history.create_indexes([
        IndexModel([("search_type", ASCENDING)], name="search_history_type"),
        IndexModel([("created_at", DESCENDING)], name="search_history_created_at"),
    ])

    await db.profile_candidates.create_indexes([
        IndexModel([("full_name", TEXT), ("company_name", TEXT)], name="profile_candidates_text"),
        IndexModel([("verification_status", ASCENDING)], name="profile_candidates_status"),
        IndexModel([("created_at", DESCENDING)], name="profile_candidates_created_at"),
    ])

    logger.info("All MongoDB indexes created successfully.")