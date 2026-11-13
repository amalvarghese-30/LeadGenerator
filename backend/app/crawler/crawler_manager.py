"""
Website Crawler Engine — enhanced.

- Per-page structured results
- Playwright fallback for JS-heavy pages
- Correct counters (attempted / crawled / failed / skipped)
- SSRF + robots enforcement per request
- Concurrency + per-domain delay
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from bson import ObjectId
import httpx

from app.utils.ssrf_guard import is_safe_url
from app.discovery.robots import RobotsChecker
from app.crawler.content_extractor import ContentExtractor

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
    ):
        self.max_pages = max_pages
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.user_agent = user_agent
        self.concurrency = concurrency
        self.enable_playwright = enable_playwright

        self.extractor = ContentExtractor()
        self.robots = RobotsChecker(user_agent=user_agent)
        self._playwright = None
        self._browser = None

    # ------------------------------------------------------------------
    # Single page fetch
    # ------------------------------------------------------------------
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        result = {
            "url": url,
            "status": "failed",
            "http_status": None,
            "page_title": "",
            "main_text": "",
            "word_count": 0,
            "extraction_method": "httpx",
            "javascript_rendered": False,
            "error": None,
            "error_type": None,
        }

        # 1. SSRF
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

        # 3. HTTP fetch
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=headers,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            ) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            result["error"] = "timeout"
            result["error_type"] = "timeout"
            return result
        except httpx.HTTPError as e:
            result["error"] = f"http_error: {str(e)[:200]}"
            result["error_type"] = "http"
            return result
        except Exception as e:
            result["error"] = f"request_error: {str(e)[:200]}"
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
            result["error_type"] = "http_status"
            return result

        if "text/html" not in content_type and "xml" not in content_type:
            result["error"] = f"non_html: {content_type}"
            result["error_type"] = "content_type"
            result["status"] = "skipped"
            return result

        # 4. Extract
        try:
            content = self.extractor.extract(resp.text, final_url)
        except Exception as e:
            result["error"] = f"extract_error: {str(e)[:200]}"
            result["error_type"] = "extract"
            return result

        word_count = int(content.get("word_count", 0))
        result.update({
            "url": final_url,
            "page_title": content.get("title", ""),
            "h1": content.get("h1", ""),
            "h2s": content.get("h2s", []),
            "main_text": content.get("main_text", ""),
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

        result["status"] = "success"
        return result

    async def _playwright_render(self, url: str) -> Optional[Dict]:
        """Render with Playwright. Returns dict with main_text/word_count/title or None."""
        try:
            if self._playwright is None:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            page = await self._browser.new_page(user_agent=self.user_agent)
            try:
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
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
            logger.debug("Playwright render failed for %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # Batch crawl
    # ------------------------------------------------------------------
    async def crawl_urls(
        self,
        urls: List[str],
        job_id: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl URLs with limited concurrency and delay.
        Updates MongoDB job counters per page.
        """
        urls = urls[: self.max_pages]
        total = len(urls)
        results: List[Dict[str, Any]] = []
        sem = asyncio.Semaphore(self.concurrency)
        counters = {"attempted": 0, "crawled": 0, "failed": 0, "skipped": 0}
        lock = asyncio.Lock()

        async def _do(idx: int, url: str):
            async with sem:
                res = await self.crawl_url(url)
                results.append(res)

                async with lock:
                    counters["attempted"] += 1
                    if res["status"] == "success":
                        counters["crawled"] += 1
                    elif res["status"] == "skipped":
                        counters["skipped"] += 1
                    else:
                        counters["failed"] += 1

                    if db is not None and job_id is not None:
                        progress = int(((idx + 1) / max(total, 1)) * 60) + 20
                        try:
                            await db.crawl_jobs.update_one(
                                {"_id": ObjectId(job_id)},
                                {
                                    "$set": {
                                        "pages_attempted": counters["attempted"],
                                        "pages_crawled": counters["crawled"],
                                        "pages_failed": counters["failed"],
                                        "pages_skipped": counters["skipped"],
                                        "progress_pct": min(progress, 80),
                                        "current_stage": "crawling",
                                        "updated_at": datetime.utcnow(),
                                    }
                                },
                            )
                        except Exception as e:
                            logger.debug("progress update failed: %s", e)

                await asyncio.sleep(self.delay_seconds)

        tasks = [asyncio.create_task(_do(i, u)) for i, u in enumerate(urls)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results