"""
Database Seeder for LeadIntel CRM.
Seeds default admin user, initial reference provider (The Person),
sample companies, contacts, client references, leads across pipeline stages,
and sample activities/tasks.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.auth.password import hash_password
from app.database.indexes import create_indexes
from app.services.scoring_service import calculate_lead_score

async def seed_database():
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    print("Creating indexes...")
    await create_indexes(db)

    now = datetime.now(timezone.utc)

    # 1. Seed Users
    print("Seeding users...")
    admin_email = "admin@leadintel.local"
    admin_user = await db.users.find_one({"email": admin_email})
    if not admin_user:
        hashed = hash_password("Admin@123456")
        res = await db.users.insert_one({
            "email": admin_email,
            "full_name": "LeadIntel Administrator",
            "hashed_password": hashed,
            "role": "admin",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        admin_id = str(res.inserted_id)
        print(f"Created default admin user: {admin_email} / Admin@123456 (ID: {admin_id})")
    else:
        admin_id = str(admin_user["_id"])
        print(f"Admin user already exists (ID: {admin_id})")

    # 2. Seed Initial Reference Provider (The Person)
    print("Seeding reference provider: The Person (theperson.in)...")
    the_person = await db.providers.find_one({"domain": "theperson.in"})
    if not the_person:
        provider_doc = {
            "name": "The Person",
            "website": "https://theperson.in/",
            "domain": "theperson.in",
            "category": "direct_competitor",
            "services": [
                "Google Knowledge Panel services",
                "Google Knowledge Panel optimisation",
                "Entity SEO services",
                "Personal entity management",
                "Personal profile publishing",
                "Google search visibility services",
                "Online identity management",
                "Digital reputation management",
                "Personal branding agency",
                "Executive branding"
            ],
            "description": "Premium personal branding, online professional visibility, personal profile publishing, digital authority and Google search visibility company.",
            "country": "India",
            "city": "Bengaluru",
            "social_links": {
                "linkedin": "https://www.linkedin.com/company/thepersonin",
                "twitter": "https://twitter.com/thepersonin",
                "instagram": "https://www.instagram.com/theperson.in",
                "facebook": "https://www.facebook.com/theperson.in"
            },
            "contact_channels": {
                "general_email": "contact@theperson.in",
                "phone": "+91 80 4000 1234",
                "contact_page": "https://theperson.in/contact"
            },
            "discovery_status": "crawled",
            "verification_status": "verified",
            "crawl_metadata": {
                "pages_crawled": 42,
                "references_discovered": 14,
                "last_crawled_at": now.isoformat()
            },
            "created_by": admin_id,
            "created_at": now,
            "updated_at": now
        }
        res = await db.providers.insert_one(provider_doc)
        the_person_id = str(res.inserted_id)
        print(f"Created reference provider: The Person (ID: {the_person_id})")
    else:
        the_person_id = str(the_person["_id"])
        print(f"The Person already exists (ID: {the_person_id})")

    # Seed an additional competitor provider
    second_provider = await db.providers.find_one({"domain": "brandauthority.io"})
    if not second_provider:
        p2_doc = {
            "name": "Brand Authority Partners",
            "website": "https://brandauthority.io",
            "domain": "brandauthority.io",
            "category": "related_service_provider",
            "services": [
                "Founder branding agencies",
                "Executive branding companies",
                "LinkedIn personal branding",
                "CEO branding services",
                "Thought leadership agencies"
            ],
            "country": "United States",
            "discovery_status": "crawled",
            "verification_status": "verified",
            "created_by": admin_id,
            "created_at": now,
            "updated_at": now
        }
        res2 = await db.providers.insert_one(p2_doc)
        p2_id = str(res2.inserted_id)
    else:
        p2_id = str(second_provider["_id"])

    # 3. Seed Sample Companies
    sample_companies = [
        {
            "name": "OmniHealth Diagnostics",
            "domain": "omnihealth.ai",
            "website": "https://omnihealth.ai",
            "industry": "Healthcare & Biotechnology",
            "employee_count": "50-200",
            "location": {"city": "Mumbai", "country": "India"},
            "linkedin_url": "https://linkedin.com/company/omnihealth-diagnostics",
            "dedup_key": "omnihealth.ai",
        },
        {
            "name": "Apex Wealth Advisory",
            "domain": "apexwealth.co",
            "website": "https://apexwealth.co",
            "industry": "Financial Services",
            "employee_count": "20-50",
            "location": {"city": "New Delhi", "country": "India"},
            "linkedin_url": "https://linkedin.com/company/apex-wealth",
            "dedup_key": "apexwealth.co",
        },
        {
            "name": "Vortex Autonomous Systems",
            "domain": "vortexrobotics.tech",
            "website": "https://vortexrobotics.tech",
            "industry": "Deep Tech & Robotics",
            "employee_count": "100-500",
            "location": {"city": "Bengaluru", "country": "India"},
            "linkedin_url": "https://linkedin.com/company/vortex-robotics",
            "dedup_key": "vortexrobotics.tech",
        },
        {
            "name": "Kreston & Finch Legal Partners",
            "domain": "krestonfinch.com",
            "website": "https://krestonfinch.com",
            "industry": "Legal & Corporate Law",
            "employee_count": "30-100",
            "location": {"city": "London", "country": "United Kingdom"},
            "linkedin_url": "https://linkedin.com/company/kreston-finch-law",
            "dedup_key": "krestonfinch.com",
        }
    ]

    company_ids = []
    for c in sample_companies:
        existing = await db.companies.find_one({"dedup_key": c["dedup_key"]})
        if not existing:
            c_doc = {
                **c,
                "created_by": admin_id,
                "created_at": now,
                "updated_at": now,
            }
            res = await db.companies.insert_one(c_doc)
            company_ids.append(str(res.inserted_id))
        else:
            company_ids.append(str(existing["_id"]))

    # 4. Seed Sample Contacts
    sample_contacts = [
        {
            "full_name": "Dr. Siddharth Malhotra",
            "designation": "Founder & Chief Executive Officer",
            "customer_category": "startup_founder",
            "company_id": company_ids[0],
            "business_contacts": {
                "email": "dr.malhotra@omnihealth.ai",
                "phone": "+91 22 6123 4567",
                "linkedin": "https://www.linkedin.com/in/drsiddharthmalhotra"
            },
            "location": {"city": "Mumbai", "country": "India"},
            "bio": "Pioneering AI radiology diagnostics in Southeast Asia. Forbes 30 Under 30 nominee.",
            "verification_status": "verified",
            "dedup_key": "dr.malhotra@omnihealth.ai",
        },
        {
            "full_name": "Meera Krishnan",
            "designation": "Managing Director",
            "customer_category": "financial_professional",
            "company_id": company_ids[1],
            "business_contacts": {
                "email": "meera.k@apexwealth.co",
                "linkedin": "https://www.linkedin.com/in/meerakrishnan-finance"
            },
            "location": {"city": "New Delhi", "country": "India"},
            "bio": "Managing $400M+ family office assets and ultra-high-net-worth portfolio management.",
            "verification_status": "verified",
            "dedup_key": "meera.k@apexwealth.co",
        },
        {
            "full_name": "Vikramaditya Sengupta",
            "designation": "Co-Founder & Chief Technology Officer",
            "customer_category": "startup_founder",
            "company_id": company_ids[2],
            "business_contacts": {
                "email": "vikram@vortexrobotics.tech",
                "linkedin": "https://www.linkedin.com/in/vikramsengupta"
            },
            "location": {"city": "Bengaluru", "country": "India"},
            "bio": "Ex-ISRO researcher building autonomous drone fleets. Keynote speaker at Global Tech Summit.",
            "verification_status": "verified",
            "dedup_key": "vikram@vortexrobotics.tech",
        },
        {
            "full_name": "Edward Finch",
            "designation": "Senior Partner & Corporate Counsel",
            "customer_category": "lawyer",
            "company_id": company_ids[3],
            "business_contacts": {
                "email": "efinch@krestonfinch.com",
                "linkedin": "https://www.linkedin.com/in/edward-finch-law"
            },
            "location": {"city": "London", "country": "United Kingdom"},
            "bio": "Commercial litigator specializing in cross-border M&A and international IP rights.",
            "verification_status": "unverified",
            "dedup_key": "efinch@krestonfinch.com",
        }
    ]

    contact_ids = []
    for ct in sample_contacts:
        existing = await db.contacts.find_one({"dedup_key": ct["dedup_key"]})
        if not existing:
            ct_doc = {
                **ct,
                "is_suppressed": False,
                "do_not_contact": False,
                "created_by": admin_id,
                "created_at": now,
                "updated_at": now,
            }
            res = await db.contacts.insert_one(ct_doc)
            contact_ids.append(str(res.inserted_id))
        else:
            contact_ids.append(str(existing["_id"]))

    # 5. Seed Provider Client References & Evidence
    references_data = [
        {
            "provider_id": the_person_id,
            "provider_name": "The Person",
            "person_name": "Dr. Siddharth Malhotra",
            "company_name": "OmniHealth Diagnostics",
            "contact_id": contact_ids[0],
            "company_id": company_ids[0],
            "relationship_type": "confirmed_client_case_study",
            "source_url": "https://theperson.in/case-studies/dr-siddharth-malhotra",
            "source_title": "Case Study: Scaling Healthcare Founder Digital Authority",
            "evidence_quote": "The Person structured Dr. Malhotra's personal brand, secured his verified Google Knowledge Panel, and established top-3 organic ranking across healthcare AI terms.",
            "confidence_score": 0.95,
            "verification_status": "verified",
            "verification_notes": "Cross-referenced with official press release and Google Knowledge Graph ID.",
            "discovered_at": now - timedelta(days=12),
        },
        {
            "provider_id": the_person_id,
            "provider_name": "The Person",
            "person_name": "Meera Krishnan",
            "company_name": "Apex Wealth Advisory",
            "contact_id": contact_ids[1],
            "company_id": company_ids[1],
            "relationship_type": "client_testimonial",
            "source_url": "https://theperson.in/testimonials",
            "source_title": "Executive Testimonials - The Person",
            "evidence_quote": "The executive reputation program transformed how institutional investors perceive our leadership. Inquiries increased by 300%.",
            "confidence_score": 0.90,
            "verification_status": "verified",
            "verification_notes": "Verified against LinkedIn company announcement.",
            "discovered_at": now - timedelta(days=8),
        },
        {
            "provider_id": the_person_id,
            "provider_name": "The Person",
            "person_name": "Vikramaditya Sengupta",
            "company_name": "Vortex Autonomous Systems",
            "contact_id": contact_ids[2],
            "company_id": company_ids[2],
            "relationship_type": "client_portfolio_reference",
            "source_url": "https://theperson.in/portfolio",
            "source_title": "Portfolio: Deep Tech Founders",
            "evidence_quote": "Delivered executive entity mapping and Wikipedia-aligned personal profile documentation for Vikramaditya Sengupta.",
            "confidence_score": 0.88,
            "verification_status": "verified",
            "verification_notes": "Published on client showcase page.",
            "discovered_at": now - timedelta(days=4),
        },
        {
            "provider_id": p2_id,
            "provider_name": "Brand Authority Partners",
            "person_name": "Edward Finch",
            "company_name": "Kreston & Finch Legal Partners",
            "contact_id": contact_ids[3],
            "company_id": company_ids[3],
            "relationship_type": "ordinary_mention",
            "source_url": "https://brandauthority.io/blog/thought-leadership-law",
            "source_title": "Thought Leadership in Corporate Law",
            "evidence_quote": "Prominent practitioners like Edward Finch represent the future of legal authority management.",
            "confidence_score": 0.65,
            "verification_status": "pending",
            "discovered_at": now - timedelta(days=1),
        }
    ]

    for ref in references_data:
        existing_ref = await db.provider_client_references.find_one({"source_url": ref["source_url"]})
        if not existing_ref:
            ref_doc = {
                **ref,
                "created_at": now,
                "updated_at": now,
            }
            await db.provider_client_references.insert_one(ref_doc)

    # 6. Seed CRM Leads across stages
    from bson import ObjectId
    stages = ["proposal_sent", "meeting_scheduled", "contacted", "discovered"]
    for idx, cid in enumerate(contact_ids):
        contact_doc = await db.contacts.find_one({"_id": ObjectId(cid)})

        existing_lead = await db.leads.find_one({"contact_id": cid})
        if not existing_lead:
            stage = stages[idx % len(stages)]
            lead_data = {
                "contact_id": cid,
                "company_id": company_ids[idx],
                "lead_source": "theperson.in" if idx < 3 else "brandauthority.io",
                "crm_stage": stage,
                "qualification_status": "qualified" if stage != "discovered" else "unqualified",
                "evidence_summary": f"Identified as client reference from {references_data[idx]['source_title']}",
                "source_urls": [references_data[idx]["source_url"]],
                "tags": ["high-authority", "knowledge-panel-candidate", "executive"],
                "created_by": admin_id,
                "created_at": now - timedelta(days=idx * 3),
                "updated_at": now,
            }
            score, breakdown = calculate_lead_score(lead_data, contact_doc or {})
            lead_data["score"] = score
            lead_data["score_breakdown"] = breakdown
            res = await db.leads.insert_one(lead_data)
            lead_id = str(res.inserted_id)
            print(f"Created Lead ({stage}, score: {score}): {sample_contacts[idx]['full_name']} (ID: {lead_id})")

            # Seed an activity
            await db.activities.insert_one({
                "lead_id": lead_id,
                "activity_type": "stage_changed",
                "description": f"Lead moved to {stage}",
                "created_by": admin_id,
                "created_at": now - timedelta(days=idx * 2),
            })

            # Seed a task
            await db.tasks.insert_one({
                "title": f"Follow-up with {sample_contacts[idx]['full_name']}",
                "description": f"Discuss executive branding portfolio and Google Knowledge Panel audit.",
                "lead_id": lead_id,
                "due_date": (now + timedelta(days=2 + idx)).isoformat(),
                "priority": "high" if score > 70 else "medium",
                "status": "pending",
                "assigned_to": admin_id,
                "created_by": admin_id,
                "created_at": now,
                "updated_at": now,
            })

    print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_database())
