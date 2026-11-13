import pytest
import pytest_asyncio
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

@pytest_asyncio.fixture(loop_scope="function")
async def test_db():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client["leadintel_test"]
    # Drop existing collections for clean state
    try:
        collections = await db.list_collection_names()
        for c in collections:
            if not c.startswith("system."):
                await db[c].delete_many({})
    except Exception:
        pass

    yield db

    try:
        collections = await db.list_collection_names()
        for c in collections:
            if not c.startswith("system."):
                await db[c].delete_many({})
    except Exception:
        pass
    client.close()
