import pytest
from unittest.mock import AsyncMock
from app.utils.job_logger import log_job_event, stream_manager


@pytest.mark.asyncio
async def test_job_event_logging_and_stream():
    mock_db = AsyncMock()
    job_id = "test-job-999"

    # Subscribe to live SSE queue
    queue = await stream_manager.subscribe(job_id)

    # Log event
    event = await log_job_event(
        mock_db,
        job_id=job_id,
        stage="crawling",
        severity="info",
        event_type="crawl_page_success",
        message="Fetched https://example.com/page",
        url="https://example.com/page",
    )

    # Verify event stored in DB
    mock_db.job_events.insert_one.assert_called_once()

    # Verify real-time broadcast to subscriber queue
    received = queue.get_nowait()
    assert received["job_id"] == job_id
    assert received["event_type"] == "crawl_page_success"
    assert received["stage"] == "crawling"
    assert received["message"] == "Fetched https://example.com/page"

    # Clean up subscription
    await stream_manager.unsubscribe(job_id, queue)
