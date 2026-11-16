"""
Competitor Intelligence Service.
- Competitor discovery via search queries, search operators, and public web directories.
- Full CRUD for competitor records.
- Competitor research execution: extracts services, social profiles, client references, and ad mentions.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.discovery.ddgs_search import DDGSSearch
from app.discovery.url_normalizer import URLNormalizer
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)


def _doc(d: Optional[Dict]) -> Optional[Dict]:
    if not d:
        return None
    res = dict(d)
    if "_id" in res:
        res["id"] = str(res.pop("_id"))
    for k in ["created_at", "updated_at", "last_research_date"]:
        if res.get(k) and hasattr(res[k], "isoformat"):
            res[k] = res[k].isoformat()
    return res


class CompetitorService:
    def __init__(self, db: Any):
        self.db = db
        self.ddgs = DDGSSearch(max_results=20)
        self.normalizer = URLNormalizer()

    async def list_competitors(
        self,
        skip: int = 0,
        limit: int = 20,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if category:
            query["business_category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"domain": {"$regex": search, "$options": "i"}},
                {"business_category": {"$regex": search, "$options": "i"}},
            ]
        total = await self.db.competitors.count_documents(query)
        cursor = self.db.competitors.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return {
            "items": [_doc(d) for d in docs],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    async def get_competitor(self, competitor_id: str) -> Optional[Dict[str, Any]]:
        try:
            d = await self.db.competitors.find_one({"_id": ObjectId(competitor_id)})
            return _doc(d)
        except Exception:
            return None

    async def create_competitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        website = data.get("website") or ""
        domain = self.normalizer.extract_domain(website) if website else None

        now = datetime.now(timezone.utc)
        doc = {
            "name": data.get("name", "").strip(),
            "website": website,
            "domain": domain,
            "business_category": data.get("business_category", "Agency / Marketing"),
            "social_profiles": data.get("social_profiles", []),
            "services": data.get("services", []),
            "ad_references": data.get("ad_references", []),
            "client_references": data.get("client_references", []),
            "evidence": data.get("evidence", []),
            "notes": data.get("notes"),
            "last_research_date": None,
            "created_at": now,
            "updated_at": now,
        }

        # Check existing domain to avoid duplicates
        if domain:
            existing = await self.db.competitors.find_one({"domain": domain})
            if existing:
                return _doc(existing)

        res = await self.db.competitors.insert_one(doc)
        doc["_id"] = res.inserted_id
        return _doc(doc)

    async def update_competitor(self, competitor_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data["updated_at"] = datetime.now(timezone.utc)
        if "website" in data and data["website"]:
            data["domain"] = self.normalizer.extract_domain(data["website"])

        try:
            res = await self.db.competitors.find_one_and_update(
                {"_id": ObjectId(competitor_id)},
                {"$set": data},
                return_document=True,
            )
            return _doc(res)
        except Exception:
            return None

    async def delete_competitor(self, competitor_id: str) -> bool:
        try:
            res = await self.db.competitors.delete_one({"_id": ObjectId(competitor_id)})
            return res.deleted_count > 0
        except Exception:
            return False

    async def discover_competitors(
        self,
        seed_terms: str,
        category: Optional[str] = None,
        region: Optional[str] = None,
        max_results: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Discovers potential competitors using search operators and keyword patterns.
        """
        query = f'"{seed_terms}" competitors OR alternatives OR agency {category or ""}'.strip()
        raw_items = self.ddgs.search(query, region=region or "wt-wt", max_results=max_results)

        discovered = []
        seen_domains = set()

        for item in raw_items:
            url = item.get("url") or ""
            if not url or not is_safe_url(url)[0]:
                continue
            domain = self.normalizer.extract_domain(url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            title = item.get("title") or ""
            snippet = item.get("snippet") or ""

            # Check if domain already saved as competitor
            existing = await self.db.competitors.find_one({"domain": domain})

            discovered.append({
                "name": title.split("-")[0].split("|")[0].strip() or domain,
                "website": url,
                "domain": domain,
                "snippet": snippet,
                "already_saved": existing is not None,
                "saved_id": str(existing["_id"]) if existing else None,
                "suggested_category": category or "Provider / Competitor",
            })

        return discovered

    async def run_competitor_research(self, competitor_id: str) -> Optional[Dict[str, Any]]:
        """
        Runs intelligence scans on a competitor: searches for social channels,
        meta ad references, and public client references.
        """
        competitor = await self.get_competitor(competitor_id)
        if not competitor:
            return None

        name = competitor.get("name")
        website = competitor.get("website")
        domain = competitor.get("domain")

        queries = [
            f'"{name}" clients OR case studies OR portfolio',
            f'"{name}" services OR solutions',
            f'site:{domain}' if domain else f'"{name}" website',
            f'"{name}" ad OR ads OR campaign OR marketing',
        ]

        found_socials = []
        found_services = set(competitor.get("services", []))
        client_refs = []
        ad_refs = []

        for q in queries:
            try:
                items = self.ddgs.search(q, max_results=5)
                for item in items:
                    u = item.get("url", "")
                    title = item.get("title", "")
                    snip = item.get("snippet", "")

                    if "linkedin.com/company" in u:
                        found_socials.append({"platform": "linkedin", "url": u})
                    elif "twitter.com" in u or "x.com" in u:
                        found_socials.append({"platform": "twitter", "url": u})
                    elif "facebook.com" in u:
                        found_socials.append({"platform": "facebook", "url": u})

                    if any(w in snip.lower() for w in ["client", "trusted by", "worked with"]):
                        client_refs.append({
                            "source_url": u,
                            "evidence": snip[:200],
                            "title": title,
                        })

                    if any(w in snip.lower() for w in ["ad", "advertising", "sponsored", "meta ads"]):
                        ad_refs.append({
                            "source_url": u,
                            "title": title,
                            "snippet": snip[:200],
                        })
            except Exception as e:
                logger.debug("Competitor query error: %s", e)

        # De-duplicate socials
        unique_socials = []
        seen_soc = set()
        for s in found_socials:
            if s["url"] not in seen_soc:
                seen_soc.add(s["url"])
                unique_socials.append(s)

        now = datetime.now(timezone.utc)
        update_data = {
            "social_profiles": unique_socials or competitor.get("social_profiles", []),
            "client_references": client_refs[:10],
            "ad_references": ad_refs[:10],
            "last_research_date": now,
            "updated_at": now,
        }

        updated = await self.update_competitor(competitor_id, update_data)
        return updated
