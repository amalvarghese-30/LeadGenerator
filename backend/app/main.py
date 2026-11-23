import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database.connection import connect_to_mongo, close_mongo_connection, get_database
from app.database.indexes import create_indexes
from app.scheduler.scheduler import start_scheduler, shutdown_scheduler
from app.api.routes import (
    auth,
    providers,
    leads,
    contacts,
    companies,
    activities,
    tasks,
    discovery,
    reports,
    exports,
    settings as settings_router,
    references,
    lead_generator,
    profile_creator,
    competitors,
    rate_limits,
)

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Global rate limiter (100 req/min default per client IP)
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info(f"Initializing {settings.APP_NAME} v{settings.APP_VERSION}...")
    try:
        await connect_to_mongo()
        db = get_database()
        await create_indexes(db)
        start_scheduler()
        logger.info(f"{settings.APP_NAME} initialized and ready.")
    except Exception as e:
        logger.warning(f"Startup notice (MongoDB/indexes): {e}")

    yield

    # Shutdown sequence
    logger.info("Gracefully shutting down services...")
    shutdown_scheduler()
    await close_mongo_connection()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="Candid Digital Intelligence & Lead Discovery Platform",
    version=settings.APP_VERSION,
    description="Provider Intelligence & CRM Lead Discovery Platform — Candid Digital (https://candiddigital.in/)",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routers
app.include_router(auth.router, prefix="/api")
app.include_router(providers.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(activities.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(references.router, prefix="/api")
app.include_router(lead_generator.router, prefix="/api")
app.include_router(profile_creator.router, prefix="/api")
app.include_router(competitors.router, prefix="/api")
app.include_router(rate_limits.router, prefix="/api")

@app.get("/api/health")
async def health_check():
    return {
        "service": "Candid Digital API",
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."}
    )
