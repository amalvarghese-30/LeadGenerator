"""
Website Crawler Engine — Enhanced.
- Fallback chain: HTTPX -> HTML extraction -> Playwright -> Selenium (optional).
- Per-domain adaptive delay and concurrency control via rate_limit_service.
- Retry logic with exponential backoff & jitter.
- Canonical URL detection and duplicate content detection.
- Graceful cancellation support between page requests.
- Guaranteed browser cleanup on shutdown or cancellation.
- SSRF and robots.txt compliance.
"""
import asyncio
import hashlib
import logging
import random
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Callable, Awaitable
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from bson import ObjectId
import httpx

from app.utils.ssrf_guard import is_safe_url
from app.discovery.robots import RobotsChecker
from app.crawler.content_extractor import ContentExtractor
from app.services.rate_limit_service import rate_limit_service
from app.utils.job_logger import log_job_event

logger = logging.getLogger(__name__)

SKIP_CONTENT_TYPES = (
    "application/pdf", "image/", "video/", "audio/",
    "application/zip", "application/octet-stream",
)

MIN_WORDS_FOR_JS_FALLBACK = 80


class CrawlerManager:
    def __init__(
        self,
        max_pages: int = 30,
        delay_seconds: float = 1.0,
        timeout: int = 25,
        user_agent: str = "LeadIntel-Researcher/1.0 (+https://leadintel.io/bot)",
        concurrency: int = 3,
        enable_playwright: bool = True,
        enable_selenium: bool = True,
    ):
        self.max_pages = max_pages
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.user_agent = user_agent
        self.concurrency = concurrency
        self.enable_playwright = enable_playwright
        self.enable_selenium = enable_selenium

        self.extractor = ContentExtractor()
        self.robots = RobotsChecker(user_agent=user_agent)
        self._playwright = None
        self._playwright_browser = None
        self._selenium_driver = None
        self._seen_content_hashes: set = set()

    async def cleanup(self):
        """Guaranteed browser cleanup."""
        if self._playwright_browser:
            try:
                await self._playwright_browser.close()
            except Exception as e:
                logger.debug("Playwright browser close error: %s", e)
            self._playwright_browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.debug("Playwright stop error: %s", e)
            self._playwright = None

        if self._selenium_driver:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._selenium_driver.quit)
            except Exception as e:
                logger.debug("Selenium driver quit error: %s", e)
            self._selenium_driver = None

    # ------------------------------------------------------------------
    # Single page fetch
    # ------------------------------------------------------------------
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        result = {
            "url": url,
            "canonical_url": None,
            "status": "failed",
            "http_status": None,
            "page_title": "",
            "main_text": "",
            "word_count": 0,
            "content_hash": None,
            "is_duplicate_content": False,
            "extraction_method": "httpx",
            "javascript_rendered": False,
            "error": None,
            "error_type": None,
        }

        # 1. SSRF Check
        is_safe, reason = is_safe_url(url)
        if not is_safe:
            result["error"] = f"ssrf_blocked: {reason}"
            result["error_type"] = "ssrf"
            result["status"] = "skipped"
            return result

        # 2. robots.txt
        try:
            allowed = await self.robots.is_allowed(url, url)
        except Exception as e:
            logger.debug("robots check failed for %s: %s", url, e)
            allowed = True
        if not allowed:
            result["error"] = "robots_disallowed"
            result["error_type"] = "robots"
            result["status"] = "skipped"
            return result

        # Consult adaptive rate limit policy
        policy = await rate_limit_service.get_domain_policy(url)
        effective_delay = max(self.delay_seconds, policy.get("recommended_delay_seconds", 1.0))

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 3. HTTP Fetch with retry logic
        resp = None
        max_retries = 2
        last_exception = None

        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers=headers,
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                ) as client:
                    resp = await client.get(url)
                    t_elapsed_ms = (time.time() - t0) * 1000

                    # Record rate limit metric
                    await rate_limit_service.record_request_metric(
                        url,
                        status_code=resp.status_code,
                        response_time_ms=t_elapsed_ms,
                        headers=dict(resp.headers),
                    )

                    # Handle 429 throttling
                    if resp.status_code == 429 and attempt < max_retries:
                        retry_after = 2
                        if "retry-after" in resp.headers:
                            try:
                                retry_after = int(resp.headers["retry-after"])
                            except ValueError:
                                pass
                        await asyncio.sleep(retry_after + random.uniform(0.1, 0.5))
                        continue

                    break
            except httpx.TimeoutException as e:
                t_elapsed_ms = (time.time() - t0) * 1000
                await rate_limit_service.record_request_metric(
                    url, status_code=None, response_time_ms=t_elapsed_ms, error_type="timeout"
                )
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1) + random.uniform(0.1, 0.3))
            except httpx.HTTPError as e:
                t_elapsed_ms = (time.time() - t0) * 1000
                await rate_limit_service.record_request_metric(
                    url, status_code=None, response_time_ms=t_elapsed_ms, error_type="http_error"
                )
                last_exception = e
                break
            except Exception as e:
                last_exception = e
                break

        if resp is None:
            if isinstance(last_exception, httpx.TimeoutException):
                result["error"] = "timeout"
                result["error_type"] = "timeout"
            else:
                result["error"] = f"request_error: {str(last_exception)[:200]}"
                result["error_type"] = "request"
            return result

        final_url = str(resp.url)
        safe_dest, dest_reason = is_safe_url(final_url)
        if not safe_dest:
            result["error"] = f"redirect_ssrf: {dest_reason}"
            result["error_type"] = "ssrf_redirect"
            result["status"] = "skipped"
            return result

        result["http_status"] = resp.status_code
        content_type = resp.headers.get("content-type", "").lower()

        if any(t in content_type for t in SKIP_CONTENT_TYPES):
            result["error"] = f"unsupported_content_type: {content_type}"
            result["error_type"] = "content_type"
            result["status"] = "skipped"
            return result

        if resp.status_code != 200:
            result["error"] = f"http_status_{resp.status_code}"
            result["error_type"] = f"http_{resp.status_code}"
            return result

        if "text/html" not in content_type and "xml" not in content_type:
            result["error"] = f"non_html: {content_type}"
            result["error_type"] = "content_type"
            result["status"] = "skipped"
            return result

        # Canonical URL detection
        canonical_url = None
        try:
            soup = BeautifulSoup(resp.text[:50000], "lxml")
            canon_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
            if canon_tag and canon_tag.get("href"):
                canonical_url = urljoin(final_url, canon_tag["href"].strip())
                result["canonical_url"] = canonical_url
        except Exception:
            pass

        # 4. Normal HTML Extraction
        try:
            content = self.extractor.extract(resp.text, final_url)
        except Exception as e:
            result["error"] = f"extract_error: {str(e)[:200]}"
            result["error_type"] = "extract"
            return result

        word_count = int(content.get("word_count", 0))
        main_text = content.get("main_text", "")

        result.update({
            "url": final_url,
            "page_title": content.get("title", ""),
            "h1": content.get("h1", ""),
            "h2s": content.get("h2s", []),
            "main_text": main_text,
            "word_count": word_count,
            "public_emails": content.get("public_emails", []),
            "social_profiles": content.get("social_profiles", []),
            "schema_persons": content.get("schema_persons", []),
            "schema_organizations": content.get("schema_organizations", []),
        })

        # 5. Playwright fallback if content is thin
        if word_count < MIN_WORDS_FOR_JS_FALLBACK and self.enable_playwright:
            rendered = await self._playwright_render(final_url)
            if rendered and rendered.get("word_count", 0) > word_count:
                result.update({
                    "main_text": rendered["main_text"],
                    "word_count": rendered["word_count"],
                    "extraction_method": "playwright",
                    "javascript_rendered": True,
                    "page_title": rendered.get("title") or result["page_title"],
                })
                word_count = rendered["word_count"]
                main_text = rendered["main_text"]
            # 6. Optional Selenium fallback if Playwright fails or is disabled/unavailable
            elif self.enable_selenium:
                sel_rendered = await self._selenium_render(final_url)
                if sel_rendered and sel_rendered.get("word_count", 0) > word_count:
                    result.update({
                        "main_text": sel_rendered["main_text"],
                        "word_count": sel_rendered["word_count"],
                        "extraction_method": "selenium",
                        "javascript_rendered": True,
                        "page_title": sel_rendered.get("title") or result["page_title"],
                    })
                    word_count = sel_rendered["word_count"]
                    main_text = sel_rendered["main_text"]

        # Duplicate content check
        if main_text:
            text_hash = hashlib.md5(main_text.strip().lower().encode("utf-8")).hexdigest()
            result["content_hash"] = text_hash
            if text_hash in self._seen_content_hashes:
                result["is_duplicate_content"] = True
            else:
                self._seen_content_hashes.add(text_hash)

        result["status"] = "success"
        return result

    async def _playwright_render(self, url: str) -> Optional[Dict]:
        """Render using Playwright."""
        try:
            from playwright.async_api import async_playwright
            if self._playwright is None:
                self._playwright = await async_playwright().start()
                self._playwright_browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            page = await self._playwright_browser.new_page(user_agent=self.user_agent)
            try:
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
                html = await page.content()
                title = await page.title()
            finally:
                await page.close()

            content = self.extractor.extract(html, url)
            return {
                "main_text": content.get("main_text", ""),
                "word_count": int(content.get("word_count", 0)),
                "title": title or content.get("title", ""),
            }
        except Exception as e:
            logger.debug("Playwright render unavailable/failed for %s: %s", url, e)
            return None

    async def _selenium_render(self, url: str) -> Optional[Dict]:
        """Render using Selenium fallback if required."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            def _sync_fetch():
                opts = Options()
                opts.add_argument("--headless=new")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument(f"user-agent={self.user_agent}")
                driver = webdriver.Chrome(options=opts)
                try:
                    driver.set_page_load_timeout(15)
                    driver.get(url)
                    time.sleep(1)
                    source = driver.page_source
                    title = driver.title
                    return source, title
                finally:
                    driver.quit()

            loop = asyncio.get_event_loop()
            html, title = await loop.run_in_executor(None, _sync_fetch)
            content = self.extractor.extract(html, url)
            return {
                "main_text": content.get("main_text", ""),
                "word_count": int(content.get("word_count", 0)),
                "title": title or content.get("title", ""),
            }
        except Exception as e:
            logger.debug("Selenium render unavailable/failed for %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # Batch crawl with cancellation check
    # ------------------------------------------------------------------
    async def crawl_urls(
        self,
        urls: List[str],
        job_id: Optional[str] = None,
        db: Optional[Any] = None,
        is_cancelled_fn: Optional[Callable[[], Awaitable[bool]]] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl URLs sequentially / bounded concurrency, respecting per-domain rate limits
        and actively verifying cancellation between each page fetch.
        """
        limit = max_pages or self.max_pages
        urls = urls[:limit]
        total = len(urls)
        results: List[Dict[str, Any]] = []
        counters = {"attempted": 0, "crawled": 0, "failed": 0, "skipped": 0}

        try:
            for idx, url in enumerate(urls):
                # 1. Check for job cancellation
                if is_cancelled_fn and await is_cancelled_fn():
                    logger.info("CrawlerManager: Job %s cancelled during page crawl. Halting.", job_id)
                    break

                res = await self.crawl_url(url)
                results.append(res)

                counters["attempted"] += 1
                if res["status"] == "success":
                    counters["crawled"] += 1
                    if db is not None and job_id is not None:
                        await log_job_event(
                            db, job_id, "crawling", "info", "crawl_page_success",
                            f"Crawled {url} ({res['word_count']} words, method={res['extraction_method']})",
                            url=url
                        )
                elif res["status"] == "skipped":
                    counters["skipped"] += 1
                else:
                    counters["failed"] += 1
                    if db is not None and job_id is not None:
                        await log_job_event(
                            db, job_id, "crawling", "warning", "crawl_page_failed",
                            f"Failed {url}: {res['error']}",
                            url=url
                        )

                # Update job progress in DB
                if db is not None and job_id is not None:
                    progress = int(((idx + 1) / max(total, 1)) * 35) + 25
                    try:
                        await db.crawl_jobs.update_one(
                            {"_id": ObjectId(job_id)},
                            {
                                "$set": {
                                    "pages_attempted": counters["attempted"],
                                    "pages_crawled": counters["crawled"],
                                    "pages_failed": counters["failed"],
                                    "pages_skipped": counters["skipped"],
                                    "progress_pct": min(progress, 60),
                                    "current_stage": "crawling",
                                    "updated_at": datetime.now(timezone.utc),
                                }
                            },
                        )
                    except Exception as e:
                        logger.debug("progress update failed: %s", e)

                # Delay between requests
                policy = await rate_limit_service.get_domain_policy(url)
                sleep_sec = max(self.delay_seconds, policy.get("recommended_delay_seconds", 1.0))
                await asyncio.sleep(sleep_sec)

        finally:
            await self.cleanup()

        return results
