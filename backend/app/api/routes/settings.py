from typing import Dict, Any
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.config import settings
from app.integrations.registry import IntegrationRegistry
from app.utils.secret_masker import mask_secrets

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("")
@router.get("/", include_in_schema=False)
async def get_settings_route(
    _user: dict = Depends(get_current_user),
):
    """Return public application configuration. Secrets are strictly masked."""
    config_dict = {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "crawler": {
            "max_concurrent": settings.CRAWLER_MAX_CONCURRENT,
            "request_timeout": settings.CRAWLER_REQUEST_TIMEOUT,
            "user_agent": settings.CRAWLER_USER_AGENT,
            "delay_seconds": settings.CRAWLER_DELAY_SECONDS,
            "max_retries": settings.CRAWLER_MAX_RETRIES,
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

@router.get("/integrations")
async def get_integrations_health(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Check and return health status of all integrations. Never returns secret keys."""
    registry = IntegrationRegistry(db)
    statuses = await registry.get_all_statuses()
    return {"integrations": statuses}
