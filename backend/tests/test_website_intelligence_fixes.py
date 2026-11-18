import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from app.crawler.crawler_manager import CrawlerManager
from app.services.rate_limit_service import RateLimitService, HeaderAnalyzer
from app.utils.job_logger import log_job_event, stream_manager
from app.api.routes.discovery import stream_job_events, get_job_events_route


class UnboolableDatabase:
    """Simulates PyMongo / Motor Database that raises on bool(self)."""
    def __init__(self):
        self.job_events = AsyncMock()
        self.crawl_jobs = AsyncMock()
        self.domain_rate_profiles = AsyncMock()
        self.rate_limit_request_logs = AsyncMock()
        self.rate_limit_metrics = AsyncMock()
        self.rate_limit_events = AsyncMock()

    def __bool__(self):
        raise NotImplementedError("Database objects do not implement truth value testing or bool(). Please compare with None instead: database is not None")


@pytest.mark.asyncio
async def test_database_truthiness_safety():
    """Verify crawler manager never triggers Database.__bool__ on success or failure."""
    db = UnboolableDatabase()
    crawler = CrawlerManager(delay_seconds=0.0)

    # Mock crawl_url to return success
    crawler.crawl_url = AsyncMock(return_value={
        "url": "https://example.com/test",
        "status": "success",
        "word_count": 100,
        "extraction_method": "httpx",
    })

    # crawl_urls must complete without throwing NotImplementedError
    results = await crawler.crawl_urls(
        ["https://example.com/test"],
        job_id=str(ObjectId()),
        db=db,
    )
    assert len(results) == 1
    assert results[0]["status"] == "success"

    # Now mock failure
    crawler.crawl_url = AsyncMock(return_value={
        "url": "https://example.com/failed",
        "status": "failed",
        "error": "connection_error",
        "word_count": 0,
        "extraction_method": "httpx",
    })
    results_fail = await crawler.crawl_urls(
        ["https://example.com/failed"],
        job_id=str(ObjectId()),
        db=db,
    )
    assert len(results_fail) == 1
    assert results_fail[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_rate_limit_service_database_fallback():
    """Verify RateLimitService dynamically uses get_database() when self.db is None."""
    svc = RateLimitService(db=None)

    with patch("app.database.connection.get_database") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        assert svc.database is mock_db

    # When get_database fails or raises, database property returns None cleanly
    with patch("app.database.connection.get_database", side_effect=RuntimeError("no client")):
        assert svc.database is None


@pytest.mark.asyncio
async def test_header_analyzer_retry_after():
    """Verify Retry-After parser handles seconds and RFC 2822 HTTP-date formats."""
    assert HeaderAnalyzer.parse_retry_after("12") == 12
    assert HeaderAnalyzer.parse_retry_after(None) is None
    assert HeaderAnalyzer.parse_retry_after("invalid") is None

    # HTTP-date format in the future
    future_date = "Wed, 21 Oct 2099 07:28:00 GMT"
    parsed = HeaderAnalyzer.parse_retry_after(future_date)
    assert parsed is not None
    assert parsed > 1000


@pytest.mark.asyncio
async def test_log_job_event_cross_process_id_consistency():
    """Verify log_job_event sets matching Mongo _id and serializes as id."""
    mock_db = AsyncMock()
    mock_oid = ObjectId()
    mock_insert_res = MagicMock()
    mock_insert_res.inserted_id = mock_oid
    mock_db.job_events.insert_one = AsyncMock(return_value=mock_insert_res)

    job_id = str(ObjectId())
    res = await log_job_event(
        db=mock_db,
        job_id=job_id,
        stage="crawling",
        severity="info",
        event_type="test_event",
        message="Cross-process verification",
    )

    assert res["id"] == str(mock_oid)
    assert res["job_id"] == job_id
    assert res["stage"] == "crawling"


@pytest.mark.asyncio
async def test_sse_cross_process_delivery_and_close():
    """Verify SSE streaming yields events from MongoDB (worker process simulation) and closes on completion."""
    job_id = str(ObjectId())
    ev1_id = ObjectId()
    ev2_id = ObjectId()

    docs = [
        {
            "_id": ev1_id,
            "job_id": job_id,
            "stage": "discovering",
            "severity": "info",
            "event_type": "url_discovered",
            "message": "Discovered 5 URLs",
            "event_timestamp": "2026-11-18T10:00:00Z",
        },
        {
            "_id": ev2_id,
            "job_id": job_id,
            "stage": "completed",
            "severity": "success",
            "event_type": "job_completed",
            "message": "Crawl job completed successfully",
            "event_timestamp": "2026-11-18T10:01:00Z",
        },
    ]

    mock_db = AsyncMock()
    mock_cursor = MagicMock()

    async def async_iter():
        for d in docs:
            yield d

    mock_cursor.__aiter__ = lambda self: async_iter()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_db.job_events.find = MagicMock(return_value=mock_cursor)
    mock_db.crawl_jobs.find_one = AsyncMock(return_value={"_id": ObjectId(job_id), "status": "completed"})

    mock_request = AsyncMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)
    mock_request.headers = {}

    response = await stream_job_events(job_id=job_id, request=mock_request, db=mock_db)

    # Consume the generator chunks
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    full_output = "".join(chunks)
    assert f"id: {str(ev1_id)}" in full_output
    assert "event: url_discovered" in full_output
    assert f"id: {str(ev2_id)}" in full_output
    assert "event: close" in full_output


@pytest.mark.asyncio
async def test_historical_events_cursor_pagination():
    """Verify GET /jobs/{job_id}/events supports since_id and limit without fixed truncation."""
    job_id = str(ObjectId())
    mock_db = AsyncMock()

    # Generate 250 simulated events
    generated_events = [
        {"_id": ObjectId(), "job_id": job_id, "stage": "crawling", "severity": "info", "event_type": "page_success", "message": f"Page {i}", "event_timestamp": "2026-11-18T10:00:00Z"}
        for i in range(250)
    ]

    mock_find_cursor = MagicMock()
    mock_sort_cursor = MagicMock()
    mock_sort_cursor.to_list = AsyncMock(return_value=generated_events)
    mock_find_cursor.sort = MagicMock(return_value=mock_sort_cursor)
    mock_db.job_events.find = MagicMock(return_value=mock_find_cursor)

    res = await get_job_events_route(job_id=job_id, limit=500, db=mock_db, _user={"_id": "test"})
    assert len(res) == 250
    assert res[0]["message"] == "Page 0"
    assert res[249]["message"] == "Page 249"
