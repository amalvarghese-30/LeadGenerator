"""
Script to wipe all mock and crawled data from the database,
while preserving the admin user and collection indexes.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

COLLECTIONS_TO_CLEAR = [
    "providers",
    "companies",
    "contacts",
    "leads",
    "provider_client_references",
    "activities",
    "tasks",
    "crawl_jobs",
    "discovered_urls",
    "suppression_records",
]

async def clear_mock_data():
    print(f"Connecting to MongoDB at: {settings.MONGODB_URL}")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    print("Cleaning collections...")
    for col_name in COLLECTIONS_TO_CLEAR:
        res = await db[col_name].delete_many({})
        print(f" - Cleared {col_name}: {res.deleted_count} documents removed")

    users_count = await db.users.count_documents({})
    print(f"\nPreserved {users_count} user account(s) in 'users' collection.")
    print("Database is clean and ready for fresh user-initiated scans!")
    client.close()

if __name__ == "__main__":
    asyncio.run(clear_mock_data())
