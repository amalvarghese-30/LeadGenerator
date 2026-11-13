import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database
from app.config import settings

logger = logging.getLogger(__name__)

_async_client: Optional[AsyncIOMotorClient] = None
_sync_client: Optional[MongoClient] = None


async def connect_to_mongodb() -> None:
    global _async_client, _sync_client
    logger.info("Connecting to MongoDB...")
    _async_client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
        minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
    )
    _sync_client = MongoClient(
        settings.MONGODB_URL,
        maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
        minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
    )
    # Verify connection
    try:
        await _async_client.admin.command("ping")
        logger.info("MongoDB connection established.")
    except Exception as e:
        logger.warning(f"MongoDB ping failed (will retry on first query): {e}")


async def close_mongodb_connection() -> None:
    global _async_client, _sync_client
    if _async_client:
        _async_client.close()
        logger.info("Async MongoDB connection closed.")
    if _sync_client:
        _sync_client.close()
        logger.info("Sync MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    if _async_client is None:
        raise RuntimeError("MongoDB client not initialized. Call connect_to_mongodb() first.")
    return _async_client[settings.MONGODB_DB_NAME]


def get_sync_database() -> Database:
    if _sync_client is None:
        raise RuntimeError("Sync MongoDB client not initialized.")
    return _sync_client[settings.MONGODB_DB_NAME]

connect_to_mongo = connect_to_mongodb
close_mongo_connection = close_mongodb_connection



async def get_async_client() -> AsyncIOMotorClient:
    if _async_client is None:
        raise RuntimeError("MongoDB client not initialized.")
    return _async_client
