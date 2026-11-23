from app.models.activity import ActivityDocument
from app.models.audit import AuditLogDocument
from app.models.company import CompanyDocument
from app.models.contact import ContactDocument
from app.models.crawl_job import CrawlJobDocument
from app.models.evidence import EvidenceDocument
from app.models.lead import LeadDocument
from app.models.provider import ProviderDocument
from app.models.reference import ProviderClientReferenceDocument
from app.models.user import UserDocument
from app.models.job_event import JobEventDocument
from app.models.competitor import CompetitorDocument
from app.models.rate_limit import RateLimitMetric
from app.models.lead_generator import SearchHistoryDocument
from app.models.profile_candidate import ProfileCandidateDocument

# SQLAlchemy MySQL Models
from app.models.base import Base, TimestampMixin
from app.models.sql_user import User
from app.models.sql_provider import Provider
from app.models.sql_company import Company
from app.models.sql_contact import Contact
from app.models.sql_lead import Lead
from app.models.sql_reference import ProviderClientReference
from app.models.sql_crawl_job import CrawlJob
from app.models.sql_crawl_page import CrawlPage
from app.models.sql_job_event import JobEvent
from app.models.sql_report import ResearchReport
from app.models.sql_activity import Activity, Task
from app.models.sql_competitor import Competitor
from app.models.sql_rate_limit import DomainRateProfile, RateLimitRequestLog

__all__ = [
    "ActivityDocument",
    "AuditLogDocument",
    "CompanyDocument",
    "ContactDocument",
    "CrawlJobDocument",
    "EvidenceDocument",
    "LeadDocument",
    "ProviderDocument",
    "ProviderClientReferenceDocument",
    "UserDocument",
    "JobEventDocument",
    "CompetitorDocument",
    "RateLimitMetric",
    "SearchHistoryDocument",
    "ProfileCandidateDocument",
    # SQL Models
    "Base",
    "TimestampMixin",
    "User",
    "Provider",
    "Company",
    "Contact",
    "Lead",
    "ProviderClientReference",
    "CrawlJob",
    "CrawlPage",
    "JobEvent",
    "ResearchReport",
    "Activity",
    "Task",
    "Competitor",
    "DomainRateProfile",
    "RateLimitRequestLog",
]
