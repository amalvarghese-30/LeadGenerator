import pytest
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from app.crawler.crawler_manager import CrawlerManager
from app.workers.job_processor import JobProcessor


@pytest.mark.asyncio
async def test_crawler_fallbacks():
    crawler = CrawlerManager(enable_playwright=True, enable_selenium=True)

    # 1. Normal HTML extraction with adequate words
    rich_html = "<html><head><title>Success Story</title></head><body><h1>Client Case Study</h1><p>" + "word " * 150 + "</p></body></html>"
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com/cases"
        mock_resp.text = rich_html
        mock_get.return_value = mock_resp

        res = await crawler.crawl_url("https://example.com/cases")
        assert res["status"] == "success"
        assert res["extraction_method"] == "httpx"
        assert res["word_count"] >= 100

    # 2. Thin HTML -> triggers Playwright fallback
    thin_html = "<html><head><title>Client Portal</title></head><body><div id='root'>Loading...</div></body></html>"
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com/portal"
        mock_resp.text = thin_html
        mock_get.return_value = mock_resp

        with patch.object(crawler, "_playwright_render", return_value={"main_text": "rendered content " * 40, "word_count": 80, "title": "Client Portal"}):
            res_pw = await crawler.crawl_url("https://example.com/portal")
            assert res_pw["status"] == "success"
            assert res_pw["extraction_method"] == "playwright"
            assert res_pw["javascript_rendered"] is True

    # 3. Thin HTML -> Playwright fails -> triggers Selenium fallback
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com/selenium-portal"
        mock_resp.text = thin_html
        mock_get.return_value = mock_resp

        with patch.object(crawler, "_playwright_render", return_value=None):
            with patch.object(crawler, "_selenium_render", return_value={"main_text": "selenium text " * 50, "word_count": 100, "title": "Selenium Portal"}):
                res_sel = await crawler.crawl_url("https://example.com/selenium-portal")
                assert res_sel["status"] == "success"
                assert res_sel["extraction_method"] == "selenium"
                assert res_sel["javascript_rendered"] is True


@pytest.mark.asyncio
async def test_crawler_canonical_and_duplicate_content():
    crawler = CrawlerManager()

    html_with_canon = '<html><head><link rel="canonical" href="https://example.com/canonical-page" /><title>Dupe</title></head><body><p>' + "duplicate article body " * 30 + '</p></body></html>'

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com/page-1"
        mock_resp.text = html_with_canon
        mock_get.return_value = mock_resp

        r1 = await crawler.crawl_url("https://example.com/page-1")
        assert r1["canonical_url"] == "https://example.com/canonical-page"
        assert r1["is_duplicate_content"] is False

        # Crawl identical content on another URL
        mock_resp.url = "https://example.com/page-2"
        r2 = await crawler.crawl_url("https://example.com/page-2")
        assert r2["is_duplicate_content"] is True


@pytest.mark.asyncio
async def test_crawler_cancellation_during_crawl():
    crawler = CrawlerManager(delay_seconds=0.01)

    urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3", "https://example.com/4"]

    crawl_count = 0
    async def mock_crawl_url(u):
        nonlocal crawl_count
        crawl_count += 1
        return {"url": u, "status": "success", "word_count": 50, "extraction_method": "httpx"}

    crawler.crawl_url = mock_crawl_url

    # Cancel after 2 pages
    cancel_check_count = 0
    async def is_cancelled():
        nonlocal cancel_check_count
        cancel_check_count += 1
        return cancel_check_count > 2

    results = await crawler.crawl_urls(urls, is_cancelled_fn=is_cancelled)
    # Should halt early
    assert len(results) == 2
    assert crawl_count == 2


@pytest.mark.asyncio
async def test_job_processor_cancellation_checks():
    processor = JobProcessor()
    mock_db = AsyncMock()

    # Case 1: Job already marked cancelled
    mock_db.crawl_jobs.find_one = AsyncMock(return_value={"status": "cancelled"})
    is_canc = await processor.is_job_cancelled(mock_db, "507f1f77bcf86cd799439011")
    assert is_canc is True

    # Case 2: Acquire job query excludes cancelled
    mock_db.crawl_jobs.find_one_and_update = AsyncMock(return_value=None)
    job = await processor.acquire_job(mock_db)
    assert job is None

    # Check query passed to find_one_and_update
    call_args = mock_db.crawl_jobs.find_one_and_update.call_args[0]
    query = call_args[0]
    assert query["$or"][0]["status"] == "pending"
    assert query["$or"][1]["status"] == "running"
    # Never matches cancelled
