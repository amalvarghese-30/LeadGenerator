import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import get_database, connect_to_mongo, close_mongo_connection

async def show():
    await connect_to_mongo()
    db = get_database()
    contacts = await db.contacts.find({}).sort("created_at", -1).to_list(20)
    print("=" * 90)
    print("LATEST CRM CONTACTS:")
    print("=" * 90)
    for c in contacts[:15]:
        name = str(c.get("full_name") or "—")
        desig = str(c.get("designation") or "Executive")
        comp = str(c.get("company_name") or "—")
        em = c.get("email") or "Not publicly found"
        ph = c.get("phone") or "Not found"
        status = c.get("enrichment_status") or "not_started"
        print(f"{name:<25} | {desig:<25} | {comp:<25} | Status: {status}")
        print(f"   Email: {em} | Phone: {ph}")
    
    companies = await db.companies.find({}).sort("created_at", -1).to_list(50)
    print("\n" + "=" * 90)
    print("LATEST DISCOVERED CLIENT COMPANIES (FROM INDIAN AGENCIES):")
    print("=" * 90)
    for comp in companies[:35]:
        cname = str(comp.get("name") or "—")
        web = str(comp.get("website") or "—")
        ind = str(comp.get("industry") or "—")
        print(f"{cname:<35} | Industry: {ind:<20} | Website: {web}")
        
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(show())
