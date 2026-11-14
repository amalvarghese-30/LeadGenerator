import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.database.connection import get_database, connect_to_mongo, close_mongo_connection

async def clean():
    await connect_to_mongo()
    db = get_database()
    
    # 1. Vitro Naturals
    await db.contacts.update_one(
        {"company_name": "Vitro Naturals"},
        {"$set": {"email": "online@vitronaturals.com"}}
    )
    await db.companies.update_one(
        {"name": "Vitro Naturals"},
        {"$set": {"email": "online@vitronaturals.com", "public_contact.email": "online@vitronaturals.com"}}
    )
    
    # 2. Sleepy Cat
    await db.contacts.update_one(
        {"company_name": "Sleepy Cat"},
        {"$set": {"email": "info@sleepycat.in", "phone": "+918588052247"}}
    )
    await db.companies.update_one(
        {"name": "Sleepy Cat"},
        {"$set": {"email": "info@sleepycat.in", "phone": "+918588052247", "public_contact.email": "info@sleepycat.in", "public_contact.phone": "+918588052247"}}
    )
    
    # 3. Fi
    await db.contacts.update_one(
        {"company_name": "Fi"},
        {"$set": {"email": "hello@fi.money"}}
    )
    
    # 4. LiteStore
    await db.contacts.update_one(
        {"company_name": "LiteStore"},
        {"$set": {"email": "bd@litestore.in"}}
    )

    print("Successfully set accurate primary emails and phones for key brands!")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(clean())
