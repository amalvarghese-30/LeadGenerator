import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import get_database, connect_to_mongo, close_mongo_connection

async def check_sorted():
    await connect_to_mongo()
    db = get_database()
    names = [
        "Millennial Eats", "Vitro Naturals", "MensXP", "Sleepy Cat",
        "WoW Skin Science", "The Pant Project", "HARMAN India", "JBL Professional",
        "LiteStore", "Local Bard", "&Pickles", "Booked", "Fi",
        "Morris Garages India (MG Motors)"
    ]
    contacts = await db.contacts.find({"company_name": {"$in": names}}).to_list(100)
    print("=" * 95)
    print(f"Discovered StudioSorted Clients in CRM Contacts: {len(contacts)} / {len(names)}")
    print("=" * 95)
    for c in contacts:
        name = str(c.get("full_name") or "—")
        desig = str(c.get("designation") or "—")
        comp = str(c.get("company_name") or "—")
        em = str(c.get("email") or "Not publicly found")
        ph = str(c.get("phone") or "Not found")
        status = str(c.get("enrichment_status") or "not_started")
        channels = len(c.get("contact_channels") or [])
        print(f"{name:<30} | {comp:<30} | Status: {status} ({channels} channels)")
        print(f"   Email: {em} | Phone: {ph}")
    
    # Also verify leads
    leads = await db.leads.find({}).to_list(500)
    print("\n" + "=" * 95)
    print(f"Total Leads in Pipeline: {len(leads)}")
    print("=" * 95)
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(check_sorted())
