"""
Company-First Independent Enrichment Service.
Enriches company records directly by crawling official websites, discovering contact/about pages,
extracting public business emails, phone numbers, contact forms, social media profiles,
and optionally discovering decision-makers without requiring a preexisting person contact.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from bson import ObjectId
import httpx
import tldextract

from app.discovery.client_website_resolver import ClientWebsiteResolver
from app.discovery.url_normalizer import URLNormalizer
from app.discovery.social_discovery import SocialDiscovery
from app.discovery.people_discovery_service import PeopleDiscoveryService
from app.enrichment.contact_page_discovery import ContactPageDiscovery
from app.enrichment.public_email_extractor import PublicEmailExtractor, EMAIL_REGEX
from app.enrichment.public_phone_extractor import PublicPhoneExtractor, PHONE_REGEX
from app.extraction.person_profile_extractor import PersonProfileExtractor
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

DECISION_MAKER_TITLES = [
    "founder", "co-founder", "co founder", "chief executive officer", "ceo",
    "managing director", "director", "owner", "partner", "president",
    "vice president", "head of marketing", "principal",
]


class CompanyEnrichmentService:
    def __init__(self, timeout_seconds: float = 12.0, max_pages_per_company: int = 8):
        self.timeout = timeout_seconds
        self.max_pages = max_pages_per_company
        self.website_resolver = ClientWebsiteResolver(timeout_seconds=timeout_seconds)
        self.normalizer = URLNormalizer()
        self.person_extractor = PersonProfileExtractor()
        self.people_discovery = PeopleDiscoveryService()
        self.social_discovery = SocialDiscovery()

    async def enrich_company(
        self,
        db: Any,
        company_id: str,
        max_pages: Optional[int] = None,
        default_region: str = "IN",
    ) -> Dict[str, Any]:
        """
        Enrich a company directly from its official website without requiring a contact ID.
        Extracts public business emails, phones, contact forms, social links, and optional decision makers.
        """
        now = datetime.now(timezone.utc)
        max_crawl = max_pages or self.max_pages

        # 1. Fetch company document
        try:
            company = await db.companies.find_one({"_id": ObjectId(company_id)})
        except Exception:
            company = None

        if not company:
            logger.warning("[COMPANY_ENRICH] Company %s not found in DB", company_id)
            return {"status": "error", "error": "Company not found", "company_id": company_id}

        company_name = company.get("name") or "Unknown Company"
        company_website = (
            company.get("website")
            or company.get("client_website")
            or company.get("verified_website")
            or company.get("client_url")
        )

        # 2. Resolve website if missing or invalid
        if not company_website:
            logger.info("[COMPANY_ENRICH] Resolving website for '%s' (%s)", company_name, company_id)
            # Check if company has source_references with website
            ref_site = None
            if company.get("source_references"):
                first_ref_id = company["source_references"][0]
                if ObjectId.is_valid(first_ref_id):
                    r_doc = await db.provider_client_references.find_one({"_id": ObjectId(first_ref_id)})
                    if r_doc:
                        ref_site = r_doc.get("company_website") or r_doc.get("client_website") or r_doc.get("verified_website")
            res = await self.website_resolver.resolve_client_website(company_name, portfolio_url=ref_site)
            if res.get("resolved_url"):
                company_website = res["resolved_url"]
                company_domain = res.get("domain") or self.normalizer.extract_domain(company_website)
                await db.companies.update_one(
                    {"_id": ObjectId(company_id)},
                    {"$set": {
                        "website": company_website,
                        "domain": company_domain,
                        "updated_at": now,
                    }}
                )
            else:
                await db.companies.update_one(
                    {"_id": ObjectId(company_id)},
                    {"$set": {
                        "enrichment_status": "no_website",
                        "enrichment_attempts": company.get("enrichment_attempts", 0) + 1,
                        "last_enriched_at": now,
                        "updated_at": now,
                    }}
                )
                return {
                    "status": "no_website",
                    "company_id": company_id,
                    "company_name": company_name,
                    "emails": [],
                    "phones": [],
                    "socials": {"linkedin": None, "instagram": None, "facebook": None, "twitter": None, "youtube": None},
                    "message": "No verified website available for enrichment",
                }

        # 3. Mark company status as enriching
        await db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": {"enrichment_status": "enriching", "updated_at": now}}
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 4. Fetch Homepage first
        parsed_base = urlparse(company_website)
        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
        base_domain = self.normalizer.extract_domain(company_website) or ""

        pages_to_crawl: List[str] = [company_website]
        crawled_urls: Set[str] = set()

        homepage_html = ""
        try:
            safe, _ = is_safe_url(company_website)
            if safe:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                    resp = await client.get(company_website)
                    if resp.status_code == 200:
                        homepage_html = resp.text
                        crawled_urls.add(str(resp.url))
        except Exception as e:
            logger.debug("[COMPANY_ENRICH] Error fetching homepage %s: %s", company_website, e)

        # 5. Discover subpages (Contact, About, Team, Locations, Enquiry)
        discovered_paths: List[str] = []
        if homepage_html:
            discovered_paths = ContactPageDiscovery.discover_pages_from_html(homepage_html, company_website)
            # Also parse all nav/header/footer and body links with contact/about patterns
            home_soup = BeautifulSoup(homepage_html, "html.parser")
            for a in home_soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                a_text = a.get_text(strip=True).lower()
                href_l = href.lower()
                if any(k in href_l or k in a_text for k in ["contact", "contact-us", "about", "about-us", "reach-us", "get-in-touch", "enquiry"]):
                    candidate = urljoin(company_website, href)
                    if candidate.startswith(base_origin) or self.normalizer.extract_domain(candidate) == base_domain:
                        if candidate not in discovered_paths and candidate not in pages_to_crawl:
                            discovered_paths.append(candidate)

        # Add standard path fallbacks if not found in DOM
        standard_fallbacks = [
            "/contact", "/contact-us", "/about", "/about-us", "/team",
            "/our-team", "/reach-us", "/get-in-touch", "/enquiry",
        ]
        for fb in standard_fallbacks:
            candidate = urljoin(base_origin, fb)
            if candidate not in discovered_paths and candidate not in pages_to_crawl:
                discovered_paths.append(candidate)

        for p in discovered_paths:
            if len(pages_to_crawl) >= max_crawl:
                break
            if p not in pages_to_crawl:
                pages_to_crawl.append(p)

        # 6. Crawl discovered pages and extract channels
        extracted_channels: List[Dict[str, Any]] = []
        seen_channel_values: Set[str] = set()
        social_profiles: List[Dict[str, Any]] = []
        seen_social_urls: Set[str] = set()
        discovered_forms: Set[str] = set()
        decision_maker_candidates: List[Dict[str, Any]] = []

        now_iso = now.isoformat()

        for page_url in pages_to_crawl:
            if page_url in crawled_urls and page_url != company_website:
                continue

            html = homepage_html if page_url == company_website and homepage_html else ""
            if not html:
                safe, _ = is_safe_url(page_url)
                if not safe:
                    continue
                try:
                    async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                        resp = await client.get(page_url)
                        if resp.status_code == 200:
                            html = resp.text
                            crawled_urls.add(str(resp.url))
                except Exception:
                    continue

            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # A. Email extraction
            emails = PublicEmailExtractor.extract_from_html(
                html, page_url, target_company_name=company_name
            )
            for em in emails:
                val = em.value.strip().lower()
                if val not in seen_channel_values:
                    seen_channel_values.add(val)
                    extracted_channels.append({
                        "type": "email",
                        "scope": em.scope or "company_generic",
                        "value": em.value,
                        "source_url": page_url,
                        "source_type": em.source_type,
                        "evidence_quote": em.evidence_quote or f"Published on {page_url}",
                        "syntax_valid": True,
                        "source_verified": True,
                        "verification_status": "published",
                        "confidence": em.confidence or 0.85,
                        "collected_at": now_iso,
                    })

            # B. Phone extraction
            phones = PublicPhoneExtractor.extract_from_html(
                html, page_url, default_region=default_region
            )
            for ph in phones:
                val = ph.value.strip()
                if val not in seen_channel_values:
                    seen_channel_values.add(val)
                    extracted_channels.append({
                        "type": "phone",
                        "scope": ph.scope or "company_generic",
                        "value": ph.value,
                        "source_url": page_url,
                        "source_type": ph.source_type,
                        "evidence_quote": ph.evidence_quote or f"Published phone: {ph.original_text}",
                        "country_code": ph.country_code,
                        "syntax_valid": True,
                        "source_verified": True,
                        "verification_status": "published",
                        "confidence": ph.confidence or 0.8,
                        "collected_at": now_iso,
                    })

            # C. Contact forms
            for form in soup.find_all("form"):
                action = form.get("action", "")
                full_action = urljoin(page_url, action) if action else page_url
                form_text = form.get_text(separator=" ", strip=True).lower()
                if any(k in full_action.lower() or k in form_text for k in ["contact", "enquiry", "message", "support", "get in touch", "send message"]):
                    if full_action not in discovered_forms:
                        discovered_forms.add(full_action)
                        extracted_channels.append({
                            "type": "contact_form",
                            "scope": "company_generic",
                            "value": full_action,
                            "source_url": page_url,
                            "source_type": "form_action",
                            "evidence_quote": f"Public contact form on {page_url}",
                            "syntax_valid": True,
                            "source_verified": True,
                            "verification_status": "published",
                            "confidence": 0.9,
                            "collected_at": now_iso,
                        })

            # D. Social media discovery via structured SocialDiscovery
            discovered_socials = self.social_discovery.discover_from_html(html, page_url)
            for s_item in discovered_socials:
                s_url = s_item.get("url")
                if s_url and s_url not in seen_social_urls:
                    seen_social_urls.add(s_url)
                    plat_name = s_item.get("platform", "social")
                    social_profiles.append({
                        "platform": plat_name,
                        "url": s_url,
                        "handle": s_item.get("handle"),
                        "source_url": page_url,
                        "account_type": "company",
                        "verification_status": s_item.get("verification_status", "likely_official"),
                        "confidence": s_item.get("confidence", 0.85),
                    })
                    extracted_channels.append({
                        "type": "social",
                        "scope": "company_generic",
                        "value": s_url,
                        "source_url": page_url,
                        "source_type": s_item.get("extraction_method", "social_link"),
                        "evidence_quote": f"Official {plat_name} account ({s_url}) discovered from {page_url}",
                        "syntax_valid": True,
                        "source_verified": True,
                        "verification_status": s_item.get("verification_status", "published"),
                        "confidence": s_item.get("confidence", 0.85),
                        "collected_at": now_iso,
                    })

            # E. Company Description, Address, and Aliases extraction from DOM / JSON-LD
            if not company.get("description"):
                meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
                if meta_desc and meta_desc.get("content"):
                    desc_text = meta_desc["content"].strip()
                    if desc_text and len(desc_text) > 10:
                        company["description"] = desc_text[:500]

            if not company.get("address"):
                addr_tag = soup.find("address")
                if addr_tag:
                    addr_text = re.sub(r'\s+', ' ', addr_tag.get_text(separator=' ', strip=True))
                    if len(addr_text) > 8:
                        company["address"] = addr_text[:250]

            # F. People & Leadership Discovery from HTML / JSON-LD
            page_people = self.people_discovery.discover_from_html(
                html, page_url, company_name, base_domain
            )
            for p in page_people:
                if not any(d["full_name"].lower() == p["full_name"].lower() for d in decision_maker_candidates):
                    decision_maker_candidates.append(p)

        # 6B. Optional Fallback: Permitted Public Search for Company Leadership
        if len(decision_maker_candidates) < 2 and company_name:
            try:
                search_people = self.people_discovery.discover_from_search(
                    company_name, base_domain, max_queries=2
                )
                for sp in search_people:
                    if not any(d["full_name"].lower() == sp["full_name"].lower() for d in decision_maker_candidates):
                        decision_maker_candidates.append(sp)
            except Exception as se:
                logger.warning("[COMPANY_ENRICH] People search fallback failed gracefully: %s", se)

        # 7. Persist enriched data to MongoDB
        all_emails = list(dict.fromkeys([c["value"] for c in extracted_channels if c.get("type") == "email" and c.get("value")]))
        all_phones = list(dict.fromkeys([c["value"] for c in extracted_channels if c.get("type") == "phone" and c.get("value")]))

        all_socials: Dict[str, Optional[str]] = {
            "linkedin": None,
            "instagram": None,
            "facebook": None,
            "twitter": None,
            "youtube": None,
        }
        for s in social_profiles:
            plat = (s.get("platform") or "").lower()
            if plat in all_socials and not all_socials[plat] and s.get("url"):
                all_socials[plat] = s.get("url")

        primary_email = all_emails[0] if all_emails else None
        primary_phone = all_phones[0] if all_phones else None

        public_contact = dict(company.get("public_contact") or {})
        if primary_email and not public_contact.get("email"):
            public_contact["email"] = primary_email
        if primary_phone and not public_contact.get("phone"):
            public_contact["phone"] = primary_phone
        public_contact["emails"] = all_emails
        public_contact["phones"] = all_phones
        public_contact["socials"] = all_socials
        if all_socials.get("linkedin") and not public_contact.get("linkedin"):
            public_contact["linkedin"] = all_socials["linkedin"]

        # 8. Manage Contact documents and multi-company associations for identified people
        created_contacts = []
        associated_people = list(company.get("associated_people") or [])
        seen_assoc_names = {p.get("full_name", "").lower() for p in associated_people if isinstance(p, dict)}

        for dm in decision_maker_candidates:
            try:
                dm_name = dm.get("full_name")
                if not dm_name:
                    continue
                dm_norm = dm_name.lower().strip()

                # Find if contact already exists in MongoDB
                existing_contact = await db.contacts.find_one({
                    "full_name": dm_name,
                    "$or": [
                        {"company_id": company_id},
                        {"associated_companies.company_id": str(company_id)},
                        {"company_name": company_name},
                    ]
                })

                if not existing_contact:
                    assoc_entry = {
                        "company_id": str(company_id),
                        "company_name": company_name,
                        "designation": dm.get("designation") or "Executive",
                        "source": dm.get("discovery_source") or "company_leadership_enrichment",
                        "confidence": dm.get("confidence", 0.8),
                        "verification_status": dm.get("verification_status", "source_verified"),
                        "verified_at": now_iso,
                    }
                    c_doc = {
                        "company_id": company_id,
                        "company_name": company_name,
                        "full_name": dm_name,
                        "designation": dm.get("designation") or "Executive",
                        "source": dm.get("discovery_source") or "company_leadership_enrichment",
                        "verification_status": dm.get("verification_status", "source_verified"),
                        "email": dm.get("email") or (dm.get("public_emails")[0] if dm.get("public_emails") else None),
                        "phone": dm.get("phone") or (dm.get("public_phones")[0] if dm.get("public_phones") else None),
                        "linkedin_url": dm.get("linkedin_url"),
                        "professional_urls": dm.get("professional_urls") or {},
                        "evidence_quote": dm.get("evidence_quote"),
                        "associated_companies": [assoc_entry],
                        "created_at": now,
                        "updated_at": now,
                    }
                    ins_res = await db.contacts.insert_one(c_doc)
                    contact_id_str = str(ins_res.inserted_id)
                    c_doc["_id"] = contact_id_str
                    created_contacts.append(c_doc)
                else:
                    contact_id_str = str(existing_contact.get("_id", ""))
                    # Check if company is in existing contact's associated_companies
                    existing_assocs = existing_contact.get("associated_companies") or []
                    already_linked = any(str(a.get("company_id")) == str(company_id) for a in existing_assocs if isinstance(a, dict))
                    if not already_linked:
                        await db.contacts.update_one(
                            {"_id": existing_contact["_id"]},
                            {"$push": {"associated_companies": {
                                "company_id": str(company_id),
                                "company_name": company_name,
                                "designation": dm.get("designation") or "Executive",
                                "source": dm.get("discovery_source") or "company_leadership_enrichment",
                                "confidence": dm.get("confidence", 0.8),
                                "verification_status": dm.get("verification_status", "source_verified"),
                                "verified_at": now_iso,
                            }}}
                        )

                if dm_norm not in seen_assoc_names:
                    seen_assoc_names.add(dm_norm)
                    associated_people.append({
                        "contact_id": contact_id_str,
                        "full_name": dm_name,
                        "designation": dm.get("designation") or "Executive",
                        "linkedin_url": dm.get("linkedin_url"),
                        "verification_status": dm.get("verification_status", "source_verified"),
                        "confidence": dm.get("confidence", 0.8),
                    })
            except Exception as ce:
                logger.debug("[COMPANY_ENRICH] Error creating decision-maker contact: %s", ce)

        final_status = "enriched" if (extracted_channels or associated_people) else "no_contacts_found"

        update_doc: Dict[str, Any] = {
            "website": company_website,
            "emails": all_emails,
            "phones": all_phones,
            "socials": all_socials,
            "public_contact": public_contact,
            "public_contact_channels": extracted_channels,
            "social_profiles": social_profiles,
            "associated_people": associated_people,
            "enrichment_status": final_status,
            "enrichment_attempts": company.get("enrichment_attempts", 0) + 1,
            "last_enriched_at": now,
            "updated_at": now,
        }
        if company.get("description"):
            update_doc["description"] = company["description"]
        if company.get("address"):
            update_doc["address"] = company["address"]

        await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": update_doc})

        logger.info(
            "[COMPANY_ENRICH] Completed for %s: %d channels (%d emails, %d phones, %d forms, %d socials), %d decision-makers",
            company_name, len(extracted_channels),
            len(all_emails),
            len(all_phones),
            len(discovered_forms), len(social_profiles), len(decision_maker_candidates)
        )

        return {
            "company_id": company_id,
            "company_name": company_name,
            "website": company_website,
            "emails": all_emails,
            "phones": all_phones,
            "socials": all_socials,
            "status": final_status,
            "enrichment_status": final_status,
            "pages_crawled": len(crawled_urls),
            "business_emails": len(all_emails),
            "business_phones": len(all_phones),
            "contact_forms": len(discovered_forms),
            "social_links": len(social_profiles),
            "decision_makers_found": len(decision_maker_candidates),
            "contacts_created": len(created_contacts),
            "channels": extracted_channels,
            "public_contact_channels": extracted_channels,
            "social_profiles": social_profiles,
        }

    def _extract_decision_makers_from_soup(
        self,
        soup: BeautifulSoup,
        source_url: str,
        company_name: str,
    ) -> List[Dict[str, Any]]:
        """Extract executive / leadership candidates from team/about HTML."""
        candidates = []
        # Look for member cards / team blocks
        card_selectors = [
            ".team-member", ".member-card", ".leadership-card", ".bio-card",
            ".executive-card", ".profile-card", ".person-card",
        ]
        cards = soup.select(", ".join(card_selectors))
        if not cards:
            # Fallback: find headings containing known executive titles in vicinity
            for h in soup.find_all(["h3", "h4", "h5"]):
                text = h.get_text(strip=True)
                nxt = h.find_next_sibling()
                nxt_text = nxt.get_text(strip=True).lower() if nxt else ""
                if any(title in nxt_text for title in DECISION_MAKER_TITLES):
                    candidates.append({
                        "full_name": text,
                        "designation": nxt.get_text(strip=True),
                        "source_url": source_url,
                    })

        for card in cards:
            h = card.find(["h3", "h4", "h5", "strong"])
            p = card.find(class_=lambda c: c and any(k in str(c).lower() for k in ["role", "title", "designation", "pos"])) or card.find("p")
            name = h.get_text(strip=True) if h else ""
            role = p.get_text(strip=True) if p else ""
            if name and role and any(t in role.lower() for t in DECISION_MAKER_TITLES):
                candidates.append({
                    "full_name": name,
                    "designation": role,
                    "source_url": source_url,
                })

        return candidates

    async def enrich_companies_batch(
        self,
        db: Any,
        company_ids: List[str],
        max_concurrency: int = 3,
        default_region: str = "IN",
    ) -> List[Dict[str, Any]]:
        """
        Batch enrich multiple companies with concurrency limit.
        Isolates failures so an error on one company does not terminate the rest.
        """
        sem = asyncio.Semaphore(max_concurrency)
        results: List[Dict[str, Any]] = []

        async def _worker(cid: str):
            async with sem:
                try:
                    res = await self.enrich_company(db, cid, default_region=default_region)
                    return res
                except Exception as e:
                    logger.exception("[COMPANY_ENRICH_BATCH] error on %s: %s", cid, e)
                    return {"status": "error", "company_id": cid, "error": str(e)}

        tasks = [_worker(cid) for cid in company_ids if cid]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results
