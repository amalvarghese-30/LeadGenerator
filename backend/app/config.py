from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "LeadIntel CRM"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "leadintel"
    MONGODB_MAX_POOL_SIZE: int = 50
    MONGODB_MIN_POOL_SIZE: int = 5
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # NVIDIA / NIM
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-bolt-e4b"
    NVIDIA_ENABLED: bool = False

    # SearXNG
    SEARXNG_BASE_URL: Optional[str] = None
    SEARXNG_TIMEOUT: int = 10

    # Crawler settings
    CRAWLER_MAX_CONCURRENT: int = 5
    CRAWLER_REQUEST_TIMEOUT: int = 30
    CRAWLER_USER_AGENT: str = "LeadIntelBot/1.0 (+https://leadintel.io/bot)"
    CRAWLER_DELAY_SECONDS: float = 1.0
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_MAX_PAGES_PER_JOB: int = 30
    CRAWLER_CONCURRENCY: int = 3
    PLAYWRIGHT_HEADLESS: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 20

    # Scheduler
    RECRAWL_INTERVAL_DAYS: int = 7
    RSS_CHECK_INTERVAL_HOURS: int = 6
    FAILED_JOB_RETRY_INTERVAL_HOURS: int = 1

    # Security
    BCRYPT_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
