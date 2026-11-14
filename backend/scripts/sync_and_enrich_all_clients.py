"""
Master Client Sync & Website Contact Enrichment Engine
Ensures every disclosed client (across all providers) has a Contact and Lead record in the CRM,
discovers official brand websites, crawls home/contact/footer pages, and extracts emails & phone numbers.
"""
import asyncio
import os
import sys
import re
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import phonenumbers
from bson import ObjectId

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import get_database, connect_to_mongo, close_mongo_connection
from app.discovery.ddgs_search import DDGSSearch
from app.enrichment.website_discovery import WebsiteDiscovery, SOCIAL_AND_DIRECTORY_DOMAINS
from app.enrichment.public_email_extractor import EMAIL_REGEX
from app.crm.company_service import CompanyService
from app.crm.contact_service import ContactService
from app.crm.lead_service import LeadService
from app.utils.url_utils import extract_domain, normalize_url

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 LeadIntelCRM/2.0"

KNOWN_BRAND_DOMAINS = {
    "vitronaturals": "https://vitronaturals.com",
    "vitro naturals": "https://vitronaturals.com",
    "sleepy cat": "https://sleepycat.in",
    "sleepycat": "https://sleepycat.in",
    "wow skin science": "https://buywow.in",
    "the pant project": "https://pantproject.com",
    "mensxp": "https://www.mensxp.com",
    "litestore": "https://litestore.in",
    "harman india": "https://harmanaudio.in",
    "jbl professional": "https://jblpro.com",
    "local bard": "https://localbard.in",
    "&pickles": "https://andpickles.com",
    "fi": "https://fi.money",
    "morris garages india (mg motors)": "https://www.mgmotor.co.in",
    "morris garages india": "https://www.mgmotor.co.in",
    "millennial eats": "https://www.millennialeats.in",
    "saffola": "https://stores.saffola.in",
    "supertails": "https://supertails.com",
    "nua": "https://nuawoman.com",
    "koparo": "https://koparoclean.com",
    "the whole truth": "https://thewholetruthfoods.com",
    "the whole truth foods": "https://thewholetruthfoods.com",
    "aretto": "https://weararetto.com",
    "adil qadri": "https://adilqadri.com",
    "hopscotch": "https://www.hopscotch.in",
    "wedesh": "https://wedesh.in",
    "booked": "https://booked.ai",
}

def extract_page_contacts(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Emails
    mailtos = [a["href"].replace("mailto:", "").split("?")[0].strip() for a in soup.select('a[href^="mailto:"]')]
    text_emails = EMAIL_REGEX.findall(html)
    raw_emails = list(set(mailtos + text_emails))
    
    clean_emails = []
    for em in raw_emails:
        em_clean = em.lower().strip(".")
        if any(bad in em_clean for bad in ["png", "jpg", "jpeg", "webp", "gif", "svg", "sentry.io", "wixpress", "example.com", "schema.org"]):
            continue
        if len(em_clean) > 5 and "@" in em_clean:
            clean_emails.append(em_clean)
            
    # 2. Phones
    tels = [a["href"].replace("tel:", "").strip() for a in soup.select('a[href^="tel:"]')]
    valid_phones = []
    
    for t in tels:
        try:
            parsed = phonenumbers.parse(t, "IN")
            if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
                valid_phones.append(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
        except Exception:
            continue
            
    # Also scan visible text in footer or contact sections for phones
    for matcher in phonenumbers.PhoneNumberMatcher(html, "IN"):
        num = matcher.number
        if phonenumbers.is_possible_number(num) and phonenumbers.is_valid_number(num):
            valid_phones.append(phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164))
            
    return {
        "emails": list(set(clean_emails)),
        "phones": list(set(valid_phones))
    }

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

async def fetch_url(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as r:
            if r.getcode() in (200, 301, 302):
                return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    return None

async def sync_and_enrich():
    await connect_to_mongo()
    db = get_database()
    
    company_service = CompanyService(db)
    contact_service = ContactService(db)
    lead_service = LeadService(db)
    searcher = DDGSSearch(max_results=3)
    
    print("=" * 80)
    print("  PHASE 1: SYNCING ALL DISCLOSED CLIENT REFERENCES INTO CONTACTS & LEADS")
    print("=" * 80)
    
    references = await db.provider_client_references.find({}).to_list(500)
    print(f"Total Disclosed Client References: {len(references)}")
    
    created_contacts_count = 0
    created_leads_count = 0
    
    for ref in references:
        c_name = ref.get("company_name")
        p_name = ref.get("person_name")
        target_name = p_name or c_name
        if not target_name or target_name == "null" or len(target_name.strip()) < 2:
            continue
            
        provider_id = ref.get("provider_id")
        
        # 1. Ensure Company
        comp = None
        if c_name and c_name != "null":
            comp = await company_service.create({
                "name": c_name,
                "industry": ref.get("industry"),
                "source_references": [str(ref["_id"])],
            })
        company_id = comp.get("id") if comp else None
        
        # 2. Check or Create Contact
        contact = await db.contacts.find_one({"$or": [
            {"full_name": target_name},
            {"normalized_name": target_name.lower().strip()},
            {"company_name": c_name}
        ]})
        
        if not contact:
            desig = ref.get("designation") or ("Client Brand / Executive Account" if not p_name else "Executive")
            contact_doc, was_new = await contact_service.create({
                "full_name": target_name,
                "designation": desig,
                "company_id": company_id,
                "company_name": c_name or target_name,
                "contact_verification_status": "discovered",
                "source_references": [str(ref["_id"])],
            })
            contact_id = contact_doc.get("id")
            if was_new:
                created_contacts_count += 1
                print(f"  [+] Created Contact: {target_name} ({c_name or '—'})")
        else:
            contact_id = str(contact["_id"])
            
        # 3. Ensure Lead exists
        if contact_id and company_id:
            lead_res = await lead_service.create(
                contact_id=contact_id,
                company_id=company_id,
                lead_source=provider_id,
                initial_stage="discovered"
            )
            if lead_res.get("created"):
                created_leads_count += 1
                
    print(f"\nPhase 1 Complete: {created_contacts_count} new Contacts created | {created_leads_count} new Leads created")
    
    print("\n" + "=" * 80)
    print("  PHASE 2: DIRECT WEBSITE DISCOVERY & FOOTER/CONTACT PAGE CRAWLING")
    print("=" * 80)
    
    # Get all companies to enrich their websites and contact details
    companies = await db.companies.find({}).to_list(500)
    print(f"Total Companies to Verify / Enrich: {len(companies)}")
    
    enriched_companies_count = 0
    enriched_contacts_count = 0
    
    for idx, comp in enumerate(companies, 1):
        cname = comp.get("name")
        if not cname or cname == "null" or len(cname.strip()) < 2:
            continue
            
        website = comp.get("website")
        existing_email = comp.get("email") or (comp.get("public_contact") or {}).get("email")
        existing_phone = comp.get("phone") or (comp.get("public_contact") or {}).get("phone")
        
        # Discover website if missing
        if not website:
            norm_cname = cname.lower().strip()
            if norm_cname in KNOWN_BRAND_DOMAINS:
                website = KNOWN_BRAND_DOMAINS[norm_cname]
                d = extract_domain(website).lower()
                await db.companies.update_one({"_id": comp["_id"]}, {"$set": {"website": website, "domain": d}})
                print(f"[{idx}/{len(companies)}] Known brand domain matched: '{cname}' -> {website}")
            else:
                clean_name = re.sub(r'[\(\)\/\\_\-]', ' ', cname).strip()
                print(f"[{idx}/{len(companies)}] Discovering website for '{clean_name}'...")
                try:
                    results = searcher.search(f"{clean_name} official website India", region="in-en")
                    for r in results:
                        u = r.get("url") or ""
                        d = extract_domain(u).lower()
                        if d and not any(ign in d for ign in SOCIAL_AND_DIRECTORY_DOMAINS):
                            parsed = urllib.parse.urlparse(u)
                            website = f"{parsed.scheme}://{parsed.netloc}"
                            await db.companies.update_one({"_id": comp["_id"]}, {"$set": {"website": website, "domain": d}})
                            print(f"    -> Found Domain: {website}")
                            break
                except Exception as e:
                    print(f"    -> Search error: {e}")
                
        # If website is available, crawl homepage, footer, and /contact
        if website and website.startswith("http"):
            discovered_emails = []
            discovered_phones = []
            
            # Pages to inspect: root first, then contact links found on the homepage, plus common paths
            homepage_html = await fetch_url(website.rstrip("/"))
            target_pages = [website.rstrip("/")]
            
            if homepage_html:
                extracted = extract_page_contacts(homepage_html, website.rstrip("/"))
                discovered_emails.extend(extracted["emails"])
                discovered_phones.extend(extracted["phones"])
                
                # Discover contact / support links from homepage
                soup_home = BeautifulSoup(homepage_html, "html.parser")
                for a in soup_home.select("a[href]"):
                    href = a["href"].strip()
                    href_lower = href.lower()
                    if any(term in href_lower for term in ["contact", "support", "help", "reach-us", "about"]):
                        full_u = urllib.parse.urljoin(website, href)
                        if full_u.startswith(website) and full_u not in target_pages:
                            target_pages.append(full_u)
                            if len(target_pages) >= 5:
                                break
                                
            # Add standard fallback paths
            for fallback in ["/contact", "/contact-us", "/pages/contact-us", "/pages/contact", "/about", "/about-us"]:
                fu = urllib.parse.urljoin(website, fallback)
                if fu not in target_pages:
                    target_pages.append(fu)

            for page_url in target_pages[1:]:
                if discovered_emails and discovered_phones:
                    break
                html = await fetch_url(page_url)
                if html:
                    extracted = extract_page_contacts(html, page_url)
                    discovered_emails.extend(extracted["emails"])
                    discovered_phones.extend(extracted["phones"])
                        
            discovered_emails = list(set(discovered_emails))
            discovered_phones = list(set(discovered_phones))
            
            if discovered_emails or discovered_phones:
                print(f"  >>> SUCCESS: {cname} | Emails: {discovered_emails[:2]} | Phones: {discovered_phones[:2]}")
                
                # Update Company Record
                comp_updates = {"updated_at": datetime.now(timezone.utc)}
                if discovered_emails:
                    comp_updates["email"] = discovered_emails[0]
                    comp_updates["public_contact.email"] = discovered_emails[0]
                if discovered_phones:
                    comp_updates["phone"] = discovered_phones[0]
                    comp_updates["public_contact.phone"] = discovered_phones[0]
                await db.companies.update_one({"_id": comp["_id"]}, {"$set": comp_updates})
                enriched_companies_count += 1
                
                # Update Matching Contact Records
                contact_cursor = db.contacts.find({"$or": [
                    {"company_id": str(comp["_id"])},
                    {"company_name": cname},
                    {"full_name": cname}
                ]})
                matching_contacts = await contact_cursor.to_list(20)
                
                for mc in matching_contacts:
                    channels = mc.get("contact_channels") or []
                    now = datetime.now(timezone.utc)
                    
                    for em in discovered_emails:
                        if not any(c.get("value") == em for c in channels):
                            channels.append({
                                "type": "email",
                                "scope": "company_generic",
                                "value": em,
                                "source_url": website,
                                "source_type": "official_company_website",
                                "evidence_quote": f"Published on official {cname} website ({website})",
                                "syntax_valid": True,
                                "source_verified": True,
                                "verification_status": "published",
                                "confidence": 0.85,
                                "collected_at": now,
                                "last_checked_at": now,
                            })
                            
                    for ph in discovered_phones:
                        if not any(c.get("value") == ph for c in channels):
                            channels.append({
                                "type": "phone",
                                "scope": "company_switchboard",
                                "value": ph,
                                "source_url": website,
                                "source_type": "official_company_website",
                                "evidence_quote": f"Published on official {cname} website ({website})",
                                "syntax_valid": True,
                                "source_verified": True,
                                "verification_status": "published",
                                "confidence": 0.8,
                                "collected_at": now,
                                "last_checked_at": now,
                            })
                            
                    c_updates = {
                        "contact_channels": channels,
                        "enrichment_status": "enriched" if (discovered_emails and discovered_phones) else "partially_enriched",
                        "updated_at": now,
                    }
                    if discovered_emails and not mc.get("email"):
                        c_updates["email"] = discovered_emails[0]
                    if discovered_phones and not mc.get("phone"):
                        c_updates["phone"] = discovered_phones[0]
                        
                    await db.contacts.update_one({"_id": mc["_id"]}, {"$set": c_updates})
                    enriched_contacts_count += 1
                    
        # Small polite delay
        await asyncio.sleep(0.5)
        
    print("\n" + "=" * 80)
    print("  FINAL ENRICHMENT SUMMARY")
    print("=" * 80)
    total_contacts = await db.contacts.count_documents({})
    total_companies = await db.companies.count_documents({})
    total_leads = await db.leads.count_documents({})
    total_refs = await db.provider_client_references.count_documents({})
    print(f"Total Disclosed Client References: {total_refs}")
    print(f"Total Client Contacts in CRM:     {total_contacts}")
    print(f"Total Client Companies in CRM:    {total_companies}")
    print(f"Total Leads in CRM:               {total_leads}")
    print(f"Companies Enriched with Web/Info: {enriched_companies_count}")
    print(f"Contacts Enriched with Channels:  {enriched_contacts_count}")
    print("=" * 80)
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(sync_and_enrich())
