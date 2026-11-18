"""
Database Seeder for LeadIntel Platform.
Safely seeds default admin user and ensures collection indexes are built.
No mock/fake records are seeded to prevent dummy data leaks into production.
"""
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.auth.password import hash_password
from app.database.indexes import create_indexes

async def seed_database():
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    print("Creating indexes...")
    await create_indexes(db)

    now = datetime.now(timezone.utc)

    # Seed Admin User ONLY
    print("Ensuring default admin user exists...")
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
        print(f"Admin user already exists: {admin_email} (ID: {admin_id})")

    print("\nDatabase initialization complete. Ready for real competitor scans.")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_database())
