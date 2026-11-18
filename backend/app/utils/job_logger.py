"""
Persistent and real-time Event Logging System for Research Jobs.
- Writes to MongoDB `job_events` collection.
- Broadcasts in real-time to active SSE listeners via JobEventStreamManager.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobEventStreamManager:
    """Manages active async subscriber queues for live job event streaming."""

    def __init__(self):
        # job_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = []
            self._subscribers[job_id].append(queue)
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            if job_id in self._subscribers:
                if queue in self._subscribers[job_id]:
                    self._subscribers[job_id].remove(queue)
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]

    async def broadcast(self, job_id: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(job_id, []))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


stream_manager = JobEventStreamManager()


async def log_job_event(
    db: Any,
    job_id: str,
    stage: str,
    severity: str,
    event_type: str,
    message: str,
    url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persist an event to MongoDB and broadcast to real-time subscribers.
    """
    now = datetime.now(timezone.utc)
    event_doc = {
        "job_id": str(job_id),
        "event_timestamp": now,
        "stage": stage,
        "severity": severity,  # info, warning, error, success
        "event_type": event_type,
        "message": message,
        "url": url,
        "metadata": metadata or {},
    }

    try:
        if db is not None:
            res = await db.job_events.insert_one(event_doc)
            event_doc["_id"] = res.inserted_id
    except Exception as e:
        logger.warning("Failed to persist job event: %s", e)

    # Format for JSON serialization / SSE
    serialized = dict(event_doc)
    serialized["event_timestamp"] = now.isoformat()
    if "_id" in serialized:
        serialized["id"] = str(serialized.pop("_id"))
    else:
        serialized["id"] = f"ev-{int(now.timestamp() * 1000)}"

    await stream_manager.broadcast(str(job_id), serialized)
    return serialized
