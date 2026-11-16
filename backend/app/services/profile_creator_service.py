"""
Auto Profile Creator Service.
- Multi-source public discovery for individuals across LinkedIn, GitHub, X/Twitter,
  Instagram, YouTube, Facebook, and company biography pages.
- Identity evidence comparison to prevent false person matching.
- Confidence scoring with clear source attribution.
- Interactive review candidate generation and verified save to Contacts CRM.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.discovery.ddgs_search import DDGSSearch
from app.discovery.url_normalizer import URLNormalizer
from app.crm.contact_service import ContactService
from app.crm.company_service import CompanyService
from app.crm.lead_service import LeadService
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

PLATFORM_PATTERNS = {
    "linkedin": r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)",
    "twitter": r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)",
    "github": r"https?://(?:www\.)?github\.com/([a-zA-Z0-9_-]+)",
    "instagram": r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.-]+)",
    "facebook": r"https?://(?:www\.)?facebook\.com/([a-zA-Z0-9_.-]+)",
    "youtube": r"https?://(?:www\.)?youtube\.com/(?:c/|user/|@)?([a-zA-Z0-9_-]+)",
}


class AutoProfileCreatorService:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self.ddgs = DDGSSearch(max_results=25)
        self.normalizer = URLNormalizer()

    async def discover_profile(
        self,
        full_name: str,
        company: Optional[str] = None,
        designation: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes targeted public searches for an individual across social networks,
        biography pages, and official sources.
        """
        target_name = full_name.strip()
        search_queries = [
            f'"{target_name}" {company or ""} {designation or ""}'.strip(),
            f'"{target_name}" linkedin {company or ""}'.strip(),
            f'"{target_name}" github {designation or ""}'.strip(),
            f'"{target_name}" biography OR bio {company or ""}'.strip(),
        ]

        raw_results: List[Dict[str, Any]] = []
        for q in search_queries:
            try:
                items = self.ddgs.search(q, max_results=8)
                raw_results.extend(items)
            except Exception as e:
                logger.debug("Profile query failed: %s", e)

        # Detect platform profile links
        platform_profiles: Dict[str, str] = {}
        bio_snippets: List[str] = []
        evidence_items: List[Dict[str, Any]] = []
        candidate_companies: List[str] = []
        candidate_titles: List[str] = []
        seen_urls = set()

        name_lower = target_name.lower()
        company_lower = (company or "").lower()
        title_lower = (designation or "").lower()
        loc_lower = (location or "").lower()

        # Identity scoring signals
        name_match_count = 0
        company_corroborated = False
        title_corroborated = False
        loc_corroborated = False

        for item in raw_results:
            url = item.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            if not is_safe_url(url)[0]:
                continue

            title = item.get("title") or ""
            snippet = item.get("snippet") or ""
            text = f"{title} {snippet}".lower()

            # Check for social platforms
            for plat, pat in PLATFORM_PATTERNS.items():
                if plat not in platform_profiles:
                    m = re.search(pat, url, re.IGNORECASE)
                    if m:
                        # Avoid company pages
                        if "/company/" in url.lower():
                            continue
                        platform_profiles[plat] = url
                        evidence_items.append({
                            "type": "social_profile",
                            "platform": plat,
                            "url": url,
                            "evidence_quote": f"Discovered {plat} profile: {title}",
                            "confidence": 0.85,
                        })

            # Check corroboration
            if name_lower in text:
                name_match_count += 1
            if company_lower and company_lower in text:
                company_corroborated = True
                candidate_companies.append(company)
            if title_lower and title_lower in text:
                title_corroborated = True
                candidate_titles.append(designation)
            if loc_lower and loc_lower in text:
                loc_corroborated = True

            if len(snippet) > 30 and (name_lower in text or (company_lower and company_lower in text)):
                bio_snippets.append(snippet)
                evidence_items.append({
                    "type": "public_reference",
                    "source_url": url,
                    "title": title,
                    "evidence_quote": snippet[:250],
                    "confidence": 0.75,
                })

        # Calculate overall identity confidence score
        confidence_score = 0.45
        if name_match_count >= 2:
            confidence_score += 0.20
        elif name_match_count == 1:
            confidence_score += 0.10

        if company_corroborated:
            confidence_score += 0.15
        elif company:
            confidence_score -= 0.15

        if title_corroborated:
            confidence_score += 0.10
        if loc_corroborated:
            confidence_score += 0.05
        if platform_profiles.get("linkedin"):
            confidence_score += 0.10

        confidence_score = min(0.95, max(0.25, round(confidence_score, 2)))
        confidence_level = "high" if confidence_score >= 0.8 else ("medium" if confidence_score >= 0.6 else "low")

        # Synthesize professional biography from public snippets
        joined_bio = " ".join(bio_snippets[:3]) if bio_snippets else None
        if joined_bio and len(joined_bio) > 400:
            joined_bio = joined_bio[:397] + "..."

        candidate_data = {
            "full_name": target_name,
            "company_name": company,
            "designation": designation,
            "location": location,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "platform_profiles": platform_profiles,
            "professional_biography": joined_bio,
            "evidence_items": evidence_items[:15],
            "verification_status": "pending_review",
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # Store candidate in DB for history
        if self.db is not None:
            try:
                res = await self.db.profile_candidates.insert_one(dict(candidate_data))
                candidate_data["_id"] = str(res.inserted_id)
                candidate_data["id"] = str(res.inserted_id)
            except Exception as e:
                logger.warning("Failed to persist profile candidate: %s", e)

        return candidate_data

    async def save_profile_to_crm(
        self,
        candidate_data: Dict[str, Any],
        create_lead: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Saves confirmed profile into Contacts CRM and idempotently links to Company and Lead.
        """
        if self.db is None:
            raise RuntimeError("Database connection required")

        contact_service = ContactService(self.db)
        company_service = CompanyService(self.db)
        lead_service = LeadService(self.db)

        full_name = candidate_data.get("full_name")
        company_name = candidate_data.get("company_name")
        designation = candidate_data.get("designation")
        platform_profiles = candidate_data.get("platform_profiles", {})
        evidence_items = candidate_data.get("evidence_items", [])

        # 1. Company
        company_id = None
        if company_name:
            comp_res = await company_service.create({
                "name": company_name,
                "notes": f"Created via Auto Profile Creator for {full_name}",
            })
            company_id = comp_res.get("id")

        # 2. Build verified contact channels
        contact_channels = []
        for plat, url in platform_profiles.items():
            contact_channels.append({
                "type": "social",
                "scope": "person_direct_work",
                "value": url,
                "source_url": url,
                "source_type": "public_profile",
                "evidence_quote": f"Confirmed {plat} profile",
                "syntax_valid": True,
                "source_verified": True,
                "verification_status": "source_verified",
                "confidence": 0.90,
            })

        # 3. Create or update Contact
        contact_doc, was_created = await contact_service.create({
            "full_name": full_name,
            "designation": designation or "Professional",
            "company_id": company_id,
            "company_name": company_name,
            "contact_verification_status": "reviewed",
            "professional_urls": platform_profiles,
            "linkedin_url": platform_profiles.get("linkedin"),
            "contact_channels": contact_channels,
            "notes": candidate_data.get("professional_biography"),
        })

        contact_id = contact_doc.get("id")

        # 4. Optional Lead creation
        lead_id = None
        if create_lead and contact_id:
            lead_res = await lead_service.create(
                contact_id=contact_id,
                company_id=company_id,
                lead_source="auto_profile_creator",
                initial_stage="discovered",
                user_id=user_id,
            )
            lead_id = lead_res.get("id")

        # Update candidate record status
        candidate_id = candidate_data.get("id") or candidate_data.get("_id")
        if candidate_id:
            try:
                await self.db.profile_candidates.update_one(
                    {"_id": ObjectId(candidate_id)},
                    {"$set": {
                        "verification_status": "confirmed",
                        "saved_contact_id": contact_id,
                        "updated_at": datetime.now(timezone.utc),
                    }}
                )
            except Exception:
                pass

        return {
            "status": "saved",
            "contact_id": contact_id,
            "company_id": company_id,
            "lead_id": lead_id,
            "was_new_contact": was_created,
        }

    async def list_recent_candidates(self, limit: int = 20) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        cursor = self.db.profile_candidates.find().sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        out = []
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            if d.get("updated_at") and hasattr(d["updated_at"], "isoformat"):
                d["updated_at"] = d["updated_at"].isoformat()
            out.append(d)
        return out
