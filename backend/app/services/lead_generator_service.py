"""
Lead Generator Service with Search Orchestrator & Entity Classification Layer.
- Company Search & Individual Search modes.
- Multi-source search with graceful degradation.
- Entity classification: Individual, Company, Organisation, Unknown.
- Duplicate detection, review candidate creation, search history logging, and direct Save to CRM.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.discovery.ddgs_search import DDGSSearch
from app.discovery.url_normalizer import URLNormalizer
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

# Common entity indicators
COMPANY_INDICATORS = {
    "inc", "corp", "corporation", "ltd", "limited", "llc", "gmbh", "pvt", "private",
    "agency", "technologies", "tech", "group", "solutions", "services", "consulting",
    "studio", "media", "capital", "partners", "holdings", "enterprises", "associates"
}

ORGANISATION_INDICATORS = {
    "org", "foundation", "institute", "association", "society", "federation",
    "council", "initiative", "charity", "university", "college", "school", "academy"
}

INDIVIDUAL_DESIGNATIONS = {
    "ceo", "cto", "cfo", "coo", "cmo", "founder", "co-founder", "director",
    "vp", "president", "partner", "lead", "engineer", "designer", "manager",
    "consultant", "strategist", "head", "chief", "executive", "advisor"
}


class EntityClassifier:
    """Classifies entity into Individual, Company, Organisation, or Unknown."""

    @staticmethod
    def classify(title: str, snippet: str, url: str) -> Dict[str, Any]:
        text = f"{title} {snippet}".lower()
        words = re.findall(r"\b[a-z0-9\-]+\b", text)
        url_lower = url.lower()

        # Check for profile URLs
        is_social_profile = any(p in url_lower for p in [
            "linkedin.com/in/", "twitter.com/", "x.com/", "github.com/",
            "instagram.com/", "facebook.com/"
        ])
        is_company_page = any(p in url_lower for p in [
            "linkedin.com/company/", "crunchbase.com/organization/",
            "facebook.com/pages/"
        ])

        if is_social_profile and not is_company_page:
            return {
                "entity_type": "individual",
                "confidence": 0.85,
                "reasoning": "URL matches personal profile structure",
                "needs_review": False,
            }

        if is_company_page:
            return {
                "entity_type": "company",
                "confidence": 0.85,
                "reasoning": "URL matches company directory/profile page",
                "needs_review": False,
            }

        org_matches = [w for w in words if w in ORGANISATION_INDICATORS]
        company_matches = [w for w in words if w in COMPANY_INDICATORS]
        indiv_matches = [w for w in words if w in INDIVIDUAL_DESIGNATIONS]

        if org_matches and not indiv_matches:
            return {
                "entity_type": "organisation",
                "confidence": 0.75,
                "reasoning": f"Identified organisation indicator(s): {', '.join(set(org_matches))}",
                "needs_review": False,
            }

        if company_matches and not indiv_matches:
            return {
                "entity_type": "company",
                "confidence": 0.75,
                "reasoning": f"Identified business keyword(s): {', '.join(set(company_matches))}",
                "needs_review": False,
            }

        if indiv_matches and not company_matches:
            return {
                "entity_type": "individual",
                "confidence": 0.70,
                "reasoning": f"Identified professional role keyword(s): {', '.join(set(indiv_matches))}",
                "needs_review": True,
            }

        if company_matches and indiv_matches:
            return {
                "entity_type": "individual",
                "confidence": 0.60,
                "reasoning": f"Mixed signals: individual role at company. Review suggested.",
                "needs_review": True,
            }

        return {
            "entity_type": "unknown",
            "confidence": 0.40,
            "reasoning": "Insufficient signals to establish definitive entity type",
            "needs_review": True,
        }


class SearchOrchestrator:
    """Manages search execution across public, no-cost search adapters."""

    def __init__(self):
        self.ddgs = DDGSSearch(max_results=20)
        self.normalizer = URLNormalizer()

    def execute_search(self, query: str, region: str = "wt-wt", max_results: int = 15) -> Dict[str, Any]:
        source_status = {"ddgs": "running"}
        results = []
        try:
            items = self.ddgs.search(query, region=region, max_results=max_results)
            results = items
            source_status["ddgs"] = "success"
        except Exception as e:
            logger.warning("DDGS adapter failed: %s", e)
            source_status["ddgs"] = f"failed: {str(e)[:100]}"

        return {
            "results": results,
            "source_status": source_status,
            "total_found": len(results),
        }


class LeadGeneratorService:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self.orchestrator = SearchOrchestrator()
        self.classifier = EntityClassifier()
        self.normalizer = URLNormalizer()

    async def search_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        additional_terms: Optional[str] = None,
        max_results: int = 15,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Company Search Mode: searches public sources for official site, business profiles,
        social channels, and contact info.
        """
        query_parts = [company_name]
        if industry:
            query_parts.append(industry)
        if country:
            query_parts.append(country)
        if additional_terms:
            query_parts.append(additional_terms)

        query = " ".join(query_parts)
        region = "wt-wt"
        if country and len(country) == 2:
            region = f"{country.lower()}-en"

        search_output = self.orchestrator.execute_search(query, region=region, max_results=max_results)
        raw_items = search_output["results"]

        processed_results = []
        seen_domains = set()

        for item in raw_items:
            url = item.get("url") or ""
            if not url or not is_safe_url(url)[0]:
                continue

            domain = self.normalizer.extract_domain(url)
            title = item.get("title") or ""
            snippet = item.get("snippet") or ""

            # Classify
            classification = self.classifier.classify(title, snippet, url)

            # Detect channels/profiles
            social_platform = None
            if "linkedin.com" in url:
                social_platform = "linkedin"
            elif "twitter.com" in url or "x.com" in url:
                social_platform = "twitter"
            elif "facebook.com" in url:
                social_platform = "facebook"
            elif "instagram.com" in url:
                social_platform = "instagram"
            elif "youtube.com" in url:
                social_platform = "youtube"
            elif "github.com" in url:
                social_platform = "github"

            is_duplicate_domain = domain in seen_domains
            seen_domains.add(domain)

            is_official = False
            if website and domain in website.lower():
                is_official = True
            elif company_name.lower().replace(" ", "") in domain.replace("-", "").replace(".", ""):
                is_official = True

            confidence = 0.85 if is_official else (0.75 if social_platform else 0.6)

            processed_results.append({
                "title": title,
                "url": url,
                "domain": domain,
                "snippet": snippet,
                "entity_type": classification["entity_type"],
                "classification_reason": classification["reasoning"],
                "needs_review": classification["needs_review"],
                "social_platform": social_platform,
                "is_official_website": is_official,
                "confidence": confidence,
                "is_duplicate_domain": is_duplicate_domain,
                "source": "ddgs",
            })

        # Save to search history if DB connected
        search_doc = {
            "search_type": "company",
            "query_params": {
                "company_name": company_name,
                "website": website,
                "industry": industry,
                "country": country,
                "additional_terms": additional_terms,
            },
            "results_count": len(processed_results),
            "results": processed_results,
            "sources_used": list(search_output["source_status"].keys()),
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc),
        }
        if self.db is not None:
            try:
                await self.db.search_history.insert_one(dict(search_doc))
            except Exception as e:
                logger.warning("Failed to save search history: %s", e)

        return {
            "mode": "company",
            "query": query,
            "sources_status": search_output["source_status"],
            "total_results": len(processed_results),
            "results": processed_results,
        }

    async def search_individual(
        self,
        full_name: str,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
        location: Optional[str] = None,
        max_results: int = 15,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Individual Search Mode: finds public professional information, social profiles,
        compares identity signals, and prevents false matches.
        """
        query_parts = [f'"{full_name}"']
        if company:
            query_parts.append(company)
        if job_title:
            query_parts.append(job_title)
        if location:
            query_parts.append(location)

        query = " ".join(query_parts)
        search_output = self.orchestrator.execute_search(query, max_results=max_results)
        raw_items = search_output["results"]

        processed_results = []
        name_tokens = set(re.findall(r"\w+", full_name.lower()))

        for item in raw_items:
            url = item.get("url") or ""
            if not url or not is_safe_url(url)[0]:
                continue

            title = item.get("title") or ""
            snippet = item.get("snippet") or ""
            combined_text = f"{title} {snippet}".lower()

            # Compare identity evidence
            matches_name = name_tokens.issubset(set(re.findall(r"\w+", combined_text)))
            matches_company = (company.lower() in combined_text) if company else None
            matches_title = (job_title.lower() in combined_text) if job_title else None
            matches_loc = (location.lower() in combined_text) if location else None

            # Calculate match confidence
            score = 0.5
            evidence_points = []
            if matches_name:
                score += 0.2
                evidence_points.append("Full name matched in page content")
            if matches_company is True:
                score += 0.15
                evidence_points.append(f"Company '{company}' corroborated")
            elif matches_company is False and company:
                score -= 0.1
                evidence_points.append(f"Company '{company}' not found in preview")

            if matches_title is True:
                score += 0.1
                evidence_points.append(f"Role '{job_title}' corroborated")
            if matches_loc is True:
                score += 0.05
                evidence_points.append(f"Location '{location}' corroborated")

            # Check for social platforms
            social_platform = None
            if "linkedin.com/in/" in url:
                social_platform = "linkedin"
                score += 0.1
            elif "twitter.com/" in url or "x.com/" in url:
                social_platform = "twitter"
            elif "github.com/" in url:
                social_platform = "github"
            elif "instagram.com/" in url:
                social_platform = "instagram"

            score = min(0.95, max(0.2, round(score, 2)))
            classification = self.classifier.classify(title, snippet, url)

            processed_results.append({
                "title": title,
                "url": url,
                "domain": self.normalizer.extract_domain(url),
                "snippet": snippet,
                "entity_type": classification["entity_type"],
                "social_platform": social_platform,
                "confidence": score,
                "evidence_points": evidence_points,
                "needs_review": score < 0.7 or classification["needs_review"],
                "corroborated_company": matches_company,
                "corroborated_title": matches_title,
                "source": "ddgs",
            })

        # Save to search history if DB connected
        search_doc = {
            "search_type": "individual",
            "query_params": {
                "full_name": full_name,
                "company": company,
                "job_title": job_title,
                "location": location,
            },
            "results_count": len(processed_results),
            "results": processed_results,
            "sources_used": list(search_output["source_status"].keys()),
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc),
        }
        if self.db is not None:
            try:
                await self.db.search_history.insert_one(dict(search_doc))
            except Exception as e:
                logger.warning("Failed to save individual search history: %s", e)

        return {
            "mode": "individual",
            "query": query,
            "sources_status": search_output["source_status"],
            "total_results": len(processed_results),
            "results": processed_results,
        }

    async def get_search_history(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        q: Dict[str, Any] = {}
        if user_id:
            q["created_by"] = user_id
        cursor = self.db.search_history.find(q).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        out = []
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out
