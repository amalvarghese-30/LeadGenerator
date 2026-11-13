"""
Contact Enrichment Service: Master orchestrator for the public business email & phone discovery pipeline.
Executes identity resolution, domain discovery, targeted crawling, multi-signal extraction,
validation (syntax, MX, numbering-plan), deduplication, and CRM contact update.
Fully non-blocking and independently retryable.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from bson import ObjectId
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.enrichment.identity_resolver import IdentityResolver, IdentityProfile
from app.enrichment.website_discovery import WebsiteDiscovery
from app.enrichment.contact_page_discovery import ContactPageDiscovery
from app.enrichment.public_email_extractor import PublicEmailExtractor
from app.enrichment.public_phone_extractor import PublicPhoneExtractor
from app.enrichment.business_directory_discovery import BusinessDirectoryDiscovery
from app.enrichment.contact_validator import ContactValidator
from app.enrichment.contact_source_verifier import ContactSourceVerifier
from app.enrichment.enrichment_deduplication import EnrichmentDeduplication
from app.crawler.content_extractor import ContentExtractor
from app.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 LeadIntelCrawler/1.0"


class ContactEnrichmentService:
    def __init__(self):
        self.website_discovery = WebsiteDiscovery()
        self.directory_discovery = BusinessDirectoryDiscovery()
        self.content_extractor = ContentExtractor()

    async def enrich_contact(self, db: AsyncIOMotorDatabase, contact_id: str) -> Dict[str, Any]:
        """
        Enrich a single CRM contact with public business contact channels.
        Independently retryable, never throws unhandled exceptions to callers.
        """
        now = datetime.now(timezone.utc)
        result_summary = {
            "contact_id": contact_id,
            "status": "failed",
            "channels_added": 0,
            "direct_emails": 0,
            "direct_phones": 0,
            "generic_emails": 0,
            "company_phones": 0,
            "errors": [],
        }

        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        except Exception as e:
            result_summary["errors"].append(f"Invalid contact ID: {e}")
            return result_summary

        if not contact:
            result_summary["errors"].append("Contact not found")
            return result_summary

        if contact.get("is_suppressed") or contact.get("do_not_contact"):
            result_summary["status"] = "skipped_suppressed"
            return result_summary

        # Mark in_progress in DB
        await db.contacts.update_one(
            {"_id": contact["_id"]},
            {
                "$set": {
                    "enrichment_status": "in_progress",
                    "updated_at": now,
                },
                "$inc": {"enrichment_attempts": 1},
            }
        )

        try:
            # 1. Fetch associated company
            company = None
            if contact.get("company_id"):
                try:
                    company = await db.companies.find_one({"_id": ObjectId(contact["company_id"])})
                except Exception:
                    pass

            # 2. Build Identity Profile
            identity = IdentityResolver.resolve(contact, company)
            profile_dict = identity.model_dump()

            # 3. Discover Company Website if missing
            company_site = identity.company_website
            if not company_site and identity.company_name:
                company_site = self.website_discovery.discover_company_website(identity.company_name)
                if company_site and company:
                    await db.companies.update_one(
                        {"_id": company["_id"]},
                        {"$set": {"website": company_site, "domain": extract_domain(company_site), "updated_at": now}}
                    )

            # 4. Discover Personal Website if applicable
            personal_site = identity.personal_website
            if not personal_site:
                personal_site = self.website_discovery.discover_personal_website(identity.full_name, identity.company_name)

            # 5. Gather Candidate URLs to crawl
            pages_to_crawl: List[Dict[str, Any]] = []

            # 5a. Company Homepage & Contact Pages
            if company_site:
                pages_to_crawl.append({"url": company_site, "is_official": True, "type": "company_home"})
                for p in ContactPageDiscovery.get_standard_candidate_urls(company_site)[:4]:
                    pages_to_crawl.append({"url": p, "is_official": True, "type": "company_contact"})

            # 5b. Personal Website
            if personal_site:
                pages_to_crawl.append({"url": personal_site, "is_official": True, "type": "personal_home"})

            # 5c. Public Directories / Speaker Bios
            dir_matches = self.directory_discovery.search_directories(
                identity.full_name, identity.company_name, identity.designation
            )
            for dm in dir_matches:
                pages_to_crawl.append({"url": dm["url"], "is_official": False, "type": "directory"})

            # 6. Fetch & Extract from candidate pages
            discovered_raw_channels: List[Dict[str, Any]] = []

            # Pre-populate with existing channels and legacy fields to preserve them
            for ch in contact.get("contact_channels", []):
                discovered_raw_channels.append(ch)

            for plat, s_url in (contact.get("professional_urls") or {}).items():
                if s_url and s_url.startswith("http") and plat != "linkedin_handle":
                    discovered_raw_channels.append({
                        "type": "social",
                        "scope": "person_direct_work",
                        "value": s_url,
                        "source_url": s_url,
                        "source_type": "webpage",
                        "evidence_quote": f"Discovered {plat} profile",
                        "is_official": True,
                        "confidence": 0.85,
                    })

            for b_type, b_val in (contact.get("business_contacts") or {}).items():
                if b_val:
                    if "@" in b_val:
                        discovered_raw_channels.append({
                            "type": "email",
                            "scope": "person_direct_work",
                            "value": b_val,
                            "source_url": "",
                            "source_type": "webpage",
                            "evidence_quote": "Extracted business email",
                            "is_official": True,
                            "confidence": 0.8,
                        })
                    else:
                        discovered_raw_channels.append({
                            "type": "phone",
                            "scope": "person_direct_work",
                            "value": b_val,
                            "source_url": "",
                            "source_type": "webpage",
                            "evidence_quote": "Extracted business phone",
                            "is_official": True,
                            "confidence": 0.8,
                        })

            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=12.0,
                follow_redirects=True,
                verify=False
            ) as client:
                for target in pages_to_crawl[:6]:  # Cap to 6 high-value targets per contact
                    target_url = target["url"]
                    is_official = target["is_official"]

                    try:
                        resp = await client.get(target_url)
                        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                            html = resp.text

                            # Also discover additional internal contact links from homepage
                            if target["type"] == "company_home":
                                discovered_internal = ContactPageDiscovery.discover_pages_from_html(html, target_url)
                                for int_url in discovered_internal[:2]:
                                    if not any(p["url"] == int_url for p in pages_to_crawl):
                                        pages_to_crawl.append({"url": int_url, "is_official": True, "type": "company_contact"})

                            # A. Extract emails
                            emails = PublicEmailExtractor.extract_from_html(
                                html, target_url, identity.full_name, identity.company_name
                            )
                            for em in emails:
                                discovered_raw_channels.append({
                                    "type": "email",
                                    "scope": em.scope,
                                    "value": em.value,
                                    "source_url": target_url,
                                    "source_type": em.source_type,
                                    "evidence_quote": em.evidence_quote,
                                    "is_official": is_official,
                                    "confidence": em.confidence,
                                })

                            # B. Extract phones
                            phones = PublicPhoneExtractor.extract_from_html(
                                html, target_url, identity.full_name, default_region="IN"
                            )
                            for ph in phones:
                                discovered_raw_channels.append({
                                    "type": "phone",
                                    "scope": ph.scope,
                                    "value": ph.value,
                                    "source_url": target_url,
                                    "source_type": ph.source_type,
                                    "evidence_quote": ph.evidence_quote,
                                    "is_official": is_official,
                                    "confidence": ph.confidence,
                                })

                            # C. Extract contact forms
                            extracted_content = self.content_extractor.extract(html, target_url)
                            for cf in extracted_content.get("contact_forms", []):
                                discovered_raw_channels.append({
                                    "type": "contact_form",
                                    "scope": "company_generic",
                                    "value": cf,
                                    "source_url": target_url,
                                    "source_type": "webpage",
                                    "evidence_quote": "Official web contact / enquiry form",
                                    "is_official": is_official,
                                    "confidence": 0.9,
                                })
                    except Exception as crawl_err:
                        logger.debug(f"Target crawl notice for {target_url}: {crawl_err}")

            # 7. Validate and verify each discovered channel
            processed_channels: List[Dict[str, Any]] = []
            for ch in discovered_raw_channels:
                ch_type = ch.get("type")
                val = ch.get("value")
                if not val:
                    continue

                if ch_type == "email":
                    val_info = ContactValidator.validate_email_channel(
                        val, company_domain=identity.company_domain or extract_domain(company_site or "")
                    )
                    status = ContactSourceVerifier.determine_channel_status(
                        ch_type="email",
                        value=val,
                        validation_info=val_info,
                        source_url=ch.get("source_url"),
                        is_official_domain=ch.get("is_official", False),
                        has_evidence_quote=bool(ch.get("evidence_quote")),
                        human_reviewed=ch.get("human_reviewed", False),
                    )
                    processed_channels.append({
                        "type": "email",
                        "scope": ch.get("scope", "unclassified"),
                        "value": val_info["normalized_email"],
                        "source_url": ch.get("source_url"),
                        "source_type": ch.get("source_type", "webpage"),
                        "evidence_quote": ch.get("evidence_quote"),
                        "syntax_valid": val_info["syntax_valid"],
                        "mx_record_found": val_info["mx_record_found"],
                        "domain_valid": val_info["domain_valid"],
                        "source_verified": status in ("source_verified", "human_reviewed"),
                        "human_reviewed": ch.get("human_reviewed", False),
                        "confidence": ch.get("confidence", 0.5),
                        "verification_status": status,
                        "collected_at": now,
                        "last_checked_at": now,
                    })

                elif ch_type == "phone":
                    val_info = ContactValidator.validate_phone_channel(val, default_region="IN")
                    status = ContactSourceVerifier.determine_channel_status(
                        ch_type="phone",
                        value=val,
                        validation_info=val_info,
                        source_url=ch.get("source_url"),
                        is_official_domain=ch.get("is_official", False),
                        has_evidence_quote=bool(ch.get("evidence_quote")),
                        human_reviewed=ch.get("human_reviewed", False),
                    )
                    processed_channels.append({
                        "type": "phone",
                        "scope": ch.get("scope", "company_switchboard"),
                        "value": val_info.get("e164") or val,
                        "source_url": ch.get("source_url"),
                        "source_type": ch.get("source_type", "webpage"),
                        "evidence_quote": ch.get("evidence_quote"),
                        "syntax_valid": val_info["syntax_valid"],
                        "source_verified": status in ("source_verified", "human_reviewed"),
                        "human_reviewed": ch.get("human_reviewed", False),
                        "confidence": ch.get("confidence", 0.5),
                        "verification_status": status,
                        "collected_at": now,
                        "last_checked_at": now,
                    })

                elif ch_type in ("contact_form", "social", "website"):
                    processed_channels.append({
                        "type": ch_type,
                        "scope": ch.get("scope", "company_generic"),
                        "value": val,
                        "source_url": ch.get("source_url"),
                        "source_type": ch.get("source_type", "webpage"),
                        "evidence_quote": ch.get("evidence_quote"),
                        "syntax_valid": True,
                        "source_verified": ch.get("is_official", False),
                        "human_reviewed": ch.get("human_reviewed", False),
                        "confidence": ch.get("confidence", 0.8),
                        "verification_status": "source_verified" if ch.get("is_official") else "published",
                        "collected_at": now,
                        "last_checked_at": now,
                    })

            # 8. Deduplicate and prioritize channels
            final_channels = EnrichmentDeduplication.deduplicate_channels(processed_channels)

            # 9. Determine overall Contact enrichment status
            has_direct_email = any(c["type"] == "email" and c["scope"] == "person_direct_work" for c in final_channels)
            has_direct_phone = any(c["type"] == "phone" and c["scope"] == "person_direct_work" for c in final_channels)
            has_company_channel = any(c["type"] in ("email", "phone", "contact_form") for c in final_channels)

            if has_direct_email or has_direct_phone:
                final_enrichment_status = "enriched"
            elif has_company_channel:
                final_enrichment_status = "partially_enriched"
            else:
                final_enrichment_status = "no_public_contacts_found"

            # 10. Update Contact document in MongoDB
            updates: Dict[str, Any] = {
                "contact_channels": final_channels,
                "enrichment_status": final_enrichment_status,
                "last_enriched_at": now,
                "identity_profile": profile_dict,
                "updated_at": now,
            }

            # Update top-level email/phone with direct or best available
            best_email = next((c["value"] for c in final_channels if c["type"] == "email" and c["scope"] == "person_direct_work"), None)
            if not best_email:
                best_email = next((c["value"] for c in final_channels if c["type"] == "email" and c.get("verification_status") != "rejected"), None)

            best_phone = next((c["value"] for c in final_channels if c["type"] == "phone" and c["scope"] == "person_direct_work"), None)
            if not best_phone:
                best_phone = next((c["value"] for c in final_channels if c["type"] == "phone" and c.get("verification_status") != "rejected"), None)

            b_contacts = dict(contact.get("business_contacts", {}))
            if best_email:
                updates["email"] = best_email
                b_contacts["email"] = best_email
            if best_phone:
                updates["phone"] = best_phone
                b_contacts["phone"] = best_phone
            updates["business_contacts"] = b_contacts

            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": updates})

            # Tally metrics
            result_summary["status"] = final_enrichment_status
            result_summary["channels_added"] = len(final_channels)
            result_summary["direct_emails"] = sum(1 for c in final_channels if c["type"] == "email" and c["scope"] == "person_direct_work")
            result_summary["direct_phones"] = sum(1 for c in final_channels if c["type"] == "phone" and c["scope"] == "person_direct_work")
            result_summary["generic_emails"] = sum(1 for c in final_channels if c["type"] == "email" and c["scope"] != "person_direct_work")
            result_summary["company_phones"] = sum(1 for c in final_channels if c["type"] == "phone" and c["scope"] != "person_direct_work")

        except Exception as e:
            logger.exception(f"Enrichment error on contact {contact_id}: {e}")
            result_summary["errors"].append(str(e))
            await db.contacts.update_one(
                {"_id": contact["_id"]},
                {
                    "$set": {"enrichment_status": "failed", "updated_at": now},
                    "$push": {"enrichment_errors": str(e)},
                }
            )

        return result_summary

    async def enrich_contacts_batch(
        self, db: AsyncIOMotorDatabase, contact_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Batch enrichment across a list of contact IDs with concurrency control."""
        semaphore = asyncio.Semaphore(3)

        async def _run(cid: str):
            async with semaphore:
                return await self.enrich_contact(db, cid)

        tasks = [_run(cid) for cid in contact_ids]
        return await asyncio.gather(*tasks, return_exceptions=False)
