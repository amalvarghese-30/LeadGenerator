"""
Async Redis Client with distributed locking, SSE pub/sub, and rate-limit caching.
Provides graceful degradation if Redis is disabled or temporarily offline.
"""

from __future__ import annotations

import json
import logging
from typing import Optional, Any

import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Returns the singleton async Redis connection if enabled and reachable."""
    global _redis_client
    if not settings.REDIS_ENABLED:
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
            )
            await _redis_client.ping()
        except Exception as e:
            logger.warning("Redis connection failed (running in degraded memory mode): %s", e)
            _redis_client = None
    return _redis_client


async def close_redis() -> None:
    """Closes the async Redis client."""
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
        logger.info("Redis connection closed.")


# ---------- Distributed Job Locks & Cancellation Flags ----------

async def acquire_job_lock(job_id: str, worker_id: str, ttl: int = 600) -> bool:
    """Acquires a distributed mutex lock for a crawl job in Redis."""
    r = await get_redis()
    if not r:
        return True  # Gracefully allow processing if Redis not running
    try:
        result = await r.set(f"lock:job:{job_id}", worker_id, nx=True, ex=ttl)
        return bool(result)
    except Exception as e:
        logger.warning("Failed to acquire Redis job lock: %s", e)
        return True


async def release_job_lock(job_id: str) -> None:
    """Releases the distributed mutex lock for a crawl job."""
    r = await get_redis()
    if r:
        try:
            await r.delete(f"lock:job:{job_id}")
        except Exception as e:
            logger.warning("Failed to release Redis job lock: %s", e)


async def set_cancel_flag(job_id: str) -> None:
    """Sets an instant cancellation flag in Redis for running jobs."""
    r = await get_redis()
    if r:
        try:
            await r.set(f"cancel:job:{job_id}", "1", ex=3600)
        except Exception as e:
            logger.warning("Failed to set Redis cancel flag: %s", e)


async def check_cancel_flag(job_id: str) -> bool:
    """Quickly checks if a job was flagged for cancellation without hitting DB."""
    r = await get_redis()
    if not r:
        return False
    try:
        return bool(await r.exists(f"cancel:job:{job_id}"))
    except Exception:
        return False


# ---------- Real-Time SSE Event Streaming Pub/Sub ----------

async def publish_job_event(job_id: str, event_data: dict[str, Any]) -> None:
    """Publishes a live job event to Redis Pub/Sub channel for SSE consumers."""
    r = await get_redis()
    if r:
        try:
            await r.publish(f"job:{job_id}:events", json.dumps(event_data, default=str))
        except Exception as e:
            logger.debug("Redis publish event failed: %s", e)


async def subscribe_job_events(job_id: str):
    """Subscribes to a job's Redis Pub/Sub channel for zero-polling streaming."""
    r = await get_redis()
    if not r:
        return None
    try:
        pubsub = r.pubsub()
        await pubsub.subscribe(f"job:{job_id}:events")
        return pubsub
    except Exception as e:
        logger.warning("Redis pubsub subscribe failed: %s", e)
        return None


# ---------- Rate Limiting & Cooldown Cache ----------

async def get_domain_cooldown(domain: str) -> float:
    """Retrieves remaining cooldown seconds for a domain."""
    r = await get_redis()
    if not r:
        return 0.0
    try:
        val = await r.get(f"cooldown:{domain}")
        return float(val) if val else 0.0
    except Exception:
        return 0.0


async def set_domain_cooldown(domain: str, seconds: float, ttl: int = 300) -> None:
    """Caches domain cooldown duration in Redis."""
    r = await get_redis()
    if r:
        try:
            await r.set(f"cooldown:{domain}", str(seconds), ex=ttl)
        except Exception as e:
            logger.debug("Failed to set Redis domain cooldown: %s", e)
