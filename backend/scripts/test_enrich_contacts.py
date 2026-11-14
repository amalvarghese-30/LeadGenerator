import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.connection import get_database, connect_to_mongo, close_mongo_connection
from app.enrichment.contact_enrichment_service import ContactEnrichmentService

async def test():
    await connect_to_mongo()
    db = get_database()
    service = ContactEnrichmentService()
    
    contacts = await db.contacts.find({"full_name": {"$in": ["Vinay Samota", "Mubasshir Shaikh", "Dinesh Thada"]}}).to_list(10)
    for c in contacts:
        cid = str(c["_id"])
        print("\n" + "="*70)
        print(f"ENRICHING: {c.get('full_name')} | Company: {c.get('company_name')}")
        res = await service.enrich_contact(db, cid)
        print("Summary Result:", res)
        
        updated = await db.contacts.find_one({"_id": c["_id"]})
        print(f"Enrichment Status: {updated.get('enrichment_status')}")
        print(f"Total Channels: {len(updated.get('contact_channels', []))}")
        for ch in updated.get("contact_channels", []):
            print(f"  [{ch.get('type'):<12}] scope={ch.get('scope'):<18} val={ch.get('value'):<35} src={ch.get('source_type')}")
            
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(test())
