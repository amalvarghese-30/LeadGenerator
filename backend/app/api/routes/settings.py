from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.dependencies import get_db, get_current_user
from app.config import settings
from app.integrations.registry import IntegrationRegistry
from app.utils.secret_masker import mask_secrets

router = APIRouter(prefix="/settings", tags=["Settings"])


class CrawlerSettingsUpdate(BaseModel):
    delay_seconds: Optional[float] = Field(None, ge=0.1, le=60.0)
    max_pages: Optional[int] = Field(None, ge=1, le=500)
    max_concurrent: Optional[int] = Field(None, ge=1, le=20)
    request_timeout: Optional[int] = Field(None, ge=5, le=120)
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class SettingsUpdateRequest(BaseModel):
    crawler: Optional[CrawlerSettingsUpdate] = None
    app_name: Optional[str] = Field(None, max_length=100)
    notifications_enabled: Optional[bool] = None


@router.get("")
@router.get("/", include_in_schema=False)
async def get_settings_route(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Return application configuration. Secrets are strictly masked."""
    # Check if custom settings exist in MongoDB
    saved = await db.system_settings.find_one({"key": "app_config"})
    saved_crawler = saved.get("crawler", {}) if saved else {}

    config_dict = {
        "app_name": saved.get("app_name", settings.APP_NAME) if saved else settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "crawler": {
            "max_concurrent": saved_crawler.get("max_concurrent", settings.CRAWLER_MAX_CONCURRENT),
            "request_timeout": saved_crawler.get("request_timeout", settings.CRAWLER_REQUEST_TIMEOUT),
            "user_agent": settings.CRAWLER_USER_AGENT,
            "delay_seconds": saved_crawler.get("delay_seconds", settings.CRAWLER_DELAY_SECONDS),
            "max_retries": saved_crawler.get("max_retries", settings.CRAWLER_MAX_RETRIES),
            "max_pages": saved_crawler.get("max_pages", 50),
        },
        "ai": {
            "model": settings.NVIDIA_MODEL,
            "base_url": settings.NVIDIA_BASE_URL,
            "is_configured": bool(settings.NVIDIA_API_KEY),
        },
        "searxng": {
            "base_url": settings.SEARXNG_BASE_URL,
            "is_configured": bool(settings.SEARXNG_BASE_URL),
        },
        "cors_origins": settings.CORS_ORIGINS,
    }
    return mask_secrets(config_dict)


@router.put("")
@router.put("/", include_in_schema=False)
async def update_settings_route(
    data: SettingsUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update application preferences and persist them to MongoDB."""
    now = datetime.now(timezone.utc)
    update_doc: Dict[str, Any] = {
        "updated_at": now,
        "updated_by": str(user.get("_id", "")),
    }

    if data.app_name is not None:
        update_doc["app_name"] = data.app_name

    if data.crawler:
        crawler_data = {k: v for k, v in data.crawler.model_dump().items() if v is not None}
        for k, v in crawler_data.items():
            update_doc[f"crawler.{k}"] = v

    await db.system_settings.update_one(
        {"key": "app_config"},
        {"$set": update_doc},
        upsert=True,
    )

    return {"message": "Settings updated and persisted successfully"}


@router.get("/integrations")
async def get_integrations_health(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Check and return health status of all integrations. Never returns secret keys."""
    registry = IntegrationRegistry(db)
    statuses = await registry.get_all_statuses()
    return {"integrations": statuses}
