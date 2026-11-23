"""
MySQL Async Database Connection and Session Management using SQLAlchemy 2.0.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import settings
from app.models.base import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_mysql_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias for standard FastAPI dependency injection
get_db = get_mysql_db


async def init_mysql() -> None:
    """Initialize MySQL tables from SQLAlchemy declarative models."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL tables initialized successfully.")
    except Exception as e:
        logger.warning("MySQL initialization note (tables/connection): %s", e)


async def close_mysql() -> None:
    """Dispose of the MySQL database engine connection pool."""
    await engine.dispose()
    logger.info("MySQL connection pool closed.")
