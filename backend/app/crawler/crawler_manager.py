"""
Website Crawler Engine — High-Resilience Stealth Pipeline.
- Multi-stage fallback chain:
  1. Fast HTTPX with rotating stealth browser headers (Chrome/Edge 124+) & HTTP/2
  2. Cloudflare / WAF challenge / 403 / 429 / Empty SPA detection
  3. Stealth Headless Playwright (anti-detection flags, custom viewport, webdriver mask)
  4. Selenium stealth fallback
- Integrated Adaptive Rate Limiting:
  * Dynamic jittered pacing (safe_delay + random.uniform(0.5, 2.5))
  * Response header inspection (Retry-After, X-RateLimit-*, CF-Ray)
  * Metric recording & automatic domain cooldown
- Duplicate content & canonical URL handling
- SSRF protection & safe cancellation support
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
from app.utils.http_client import get_stealth_headers, is_cloudflare_or_blocked, HAS_HTTP2

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
        user_agent: Optional[str] = None,
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

        # 3. Adaptive Rate Limit Consultation & Jittered Pacing
        try:
            policy = await rate_limit_service.get_domain_policy(url)
        except Exception as e:
            logger.warning("Failed to obtain rate policy for %s: %s", url, e)
            policy = {"recommended_delay_seconds": 1.0, "is_in_cooldown": False}

        # Domain cooldown check
        if policy.get("is_in_cooldown"):
            cooldown_until_str = policy.get("cooldown_until")
            if cooldown_until_str:
                try:
                    cd_dt = datetime.fromisoformat(cooldown_until_str)
                    now = datetime.now(timezone.utc)
                    remaining = (cd_dt - now).total_seconds()
                    if remaining > 0:
                        wait_cd = min(remaining, 30.0)
                        logger.info("Domain %s in cooldown until %s. Pausing %.1fs before crawl.", url, cooldown_until_str, wait_cd)
                        await asyncio.sleep(wait_cd)
                except Exception:
                    pass

        # Dynamic jittered delay
        base_delay = max(self.delay_seconds, float(policy.get("recommended_delay_seconds") or 1.0))
        jittered_delay = base_delay + random.uniform(0.3, 1.2)
        await asyncio.sleep(jittered_delay)

        # 4. HTTP Fetch with realistic browser headers & HTTP/2
        headers = get_stealth_headers(url=url)
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

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
                    http2=HAS_HTTP2,
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
                        from app.services.rate_limit_service import HeaderAnalyzer
                        retry_after = 3.0
                        header_val = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
                        if header_val:
                            parsed_sec = HeaderAnalyzer.parse_retry_after(header_val)
                            if parsed_sec:
                                retry_after = parsed_sec
                        sleep_delay = min(retry_after + random.uniform(0.5, 1.5), 60.0)
                        logger.warning("HTTP 429 for %s. Backing off for %.1fs (attempt %d/%d)", url, sleep_delay, attempt + 1, max_retries)
                        await asyncio.sleep(sleep_delay)
                        continue

                    break
            except httpx.TimeoutException as e:
                t_elapsed_ms = (time.time() - t0) * 1000
                await rate_limit_service.record_request_metric(
                    url, status_code=None, response_time_ms=t_elapsed_ms, error_type="timeout"
                )
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1) + random.uniform(0.2, 0.5))
            except httpx.ConnectError as e:
                t_elapsed_ms = (time.time() - t0) * 1000
                await rate_limit_service.record_request_metric(
                    url, status_code=None, response_time_ms=t_elapsed_ms, error_type="connection_error"
                )
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(1.5 * (attempt + 1) + random.uniform(0.2, 0.5))
            except httpx.HTTPError as e:
                t_elapsed_ms = (time.time() - t0) * 1000
                await rate_limit_service.record_request_metric(
                    url, status_code=None, response_time_ms=t_elapsed_ms, error_type="network_error"
                )
                last_exception = e
                break
            except Exception as e:
                last_exception = e
                break

        # Check if HTTP request was completely blocked, failed, or Cloudflare challenge was returned
        needs_browser_fallback = False
        blocked_reason = ""

        if resp is None:
            needs_browser_fallback = True
            blocked_reason = "http_connection_failed"
        else:
            is_blocked, reason = is_cloudflare_or_blocked(resp.status_code, resp.text)
            if is_blocked:
                needs_browser_fallback = True
                blocked_reason = reason

        # If HTTP passed cleanly, do standard extraction first
        content = None
        final_url = str(resp.url) if resp else url
        if not needs_browser_fallback and resp and resp.status_code == 200:
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

            # Canonical URL detection
            try:
                soup = BeautifulSoup(resp.text[:50000], "lxml")
                canon_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
                if canon_tag and canon_tag.get("href"):
                    result["canonical_url"] = urljoin(final_url, canon_tag["href"].strip())
            except Exception:
                pass

            # Extract content
            try:
                content = self.extractor.extract(resp.text, final_url)
            except Exception as e:
                logger.debug("Extraction error on %s: %s", url, e)

        # Evaluate if browser fallback (Playwright / Selenium) is needed
        current_word_count = int(content.get("word_count", 0)) if content else 0
        if needs_browser_fallback or current_word_count < MIN_WORDS_FOR_JS_FALLBACK:
            rendered = None
            render_method = None

            if self.enable_playwright:
                rendered = await self._playwright_render(url)
                if rendered and rendered.get("word_count", 0) > current_word_count:
                    render_method = "playwright"

            if (not rendered or rendered.get("word_count", 0) <= current_word_count) and self.enable_selenium:
                sel_rendered = await self._selenium_render(url)
                if sel_rendered and sel_rendered.get("word_count", 0) > current_word_count:
                    rendered = sel_rendered
                    render_method = "selenium"

            if rendered and rendered.get("word_count", 0) > current_word_count:
                result.update({
                    "url": url,
                    "http_status": 200,
                    "page_title": rendered.get("title") or "",
                    "h1": rendered.get("h1", ""),
                    "h2s": rendered.get("h2s", []),
                    "main_text": rendered["main_text"],
                    "raw_html": rendered.get("raw_html", ""),
                    "word_count": rendered["word_count"],
                    "extraction_method": render_method,
                    "javascript_rendered": True,
                    "public_emails": rendered.get("public_emails", []),
                    "public_phones": rendered.get("public_phones", []),
                    "social_profiles": rendered.get("social_profiles", []),
                    "schema_persons": rendered.get("schema_persons", []),
                    "schema_organizations": rendered.get("schema_organizations", []),
                    "status": "success",
                    "error": None,
                    "error_type": None,
                })
                # Duplicate content check
                text_hash = hashlib.md5(rendered["main_text"].strip().lower().encode("utf-8")).hexdigest()
                result["content_hash"] = text_hash
                if text_hash in self._seen_content_hashes:
                    result["is_duplicate_content"] = True
                else:
                    self._seen_content_hashes.add(text_hash)
                return result

        # If HTTP extraction succeeded and no browser fallback needed or fallback was not better
        if content:
            main_text = content.get("main_text", "")
            word_count = int(content.get("word_count", 0))
            result.update({
                "url": final_url,
                "http_status": resp.status_code if resp else 200,
                "page_title": content.get("title", ""),
                "h1": content.get("h1", ""),
                "h2s": content.get("h2s", []),
                "main_text": main_text,
                "raw_html": content.get("raw_html") or (resp.text if resp else ""),
                "word_count": word_count,
                "public_emails": content.get("public_emails", []),
                "public_phones": content.get("public_phones", []),
                "social_profiles": content.get("social_profiles", []),
                "schema_persons": content.get("schema_persons", []),
                "schema_organizations": content.get("schema_organizations", []),
                "status": "success",
            })
            if main_text:
                text_hash = hashlib.md5(main_text.strip().lower().encode("utf-8")).hexdigest()
                result["content_hash"] = text_hash
                if text_hash in self._seen_content_hashes:
                    result["is_duplicate_content"] = True
                else:
                    self._seen_content_hashes.add(text_hash)
            return result

        # Both HTTP and browser fallback failed
        if resp is not None:
            result["http_status"] = resp.status_code
            result["error"] = f"blocked_or_empty: {blocked_reason or resp.status_code}"
            result["error_type"] = f"http_{resp.status_code}"
        else:
            result["error"] = f"request_error: {str(last_exception)[:200]}"
            result["error_type"] = "network_error"
        return result

    async def _playwright_render(self, url: str) -> Optional[Dict]:
        """Render using Playwright with anti-detection flags and stealth viewport."""
        try:
            from playwright.async_api import async_playwright
            if self._playwright is None:
                self._playwright = await async_playwright().start()
                self._playwright_browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-gpu",
                    ],
                )

            headers = get_stealth_headers(url=url)
            page = await self._playwright_browser.new_page(
                user_agent=self.user_agent or headers["User-Agent"],
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )

            # Mask navigator.webdriver
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

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
                "raw_html": html,
                "word_count": int(content.get("word_count", 0)),
                "title": title or content.get("title", ""),
                "h1": content.get("h1", ""),
                "h2s": content.get("h2s", []),
                "public_emails": content.get("public_emails", []),
                "public_phones": content.get("public_phones", []),
                "social_profiles": content.get("social_profiles", []),
                "schema_persons": content.get("schema_persons", []),
                "schema_organizations": content.get("schema_organizations", []),
            }
        except Exception as e:
            logger.debug("Playwright render failed for %s: %s", url, e)
            return None

    async def _selenium_render(self, url: str) -> Optional[Dict]:
        """Render using Selenium fallback if required."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            headers = get_stealth_headers(url=url)
            ua = self.user_agent or headers["User-Agent"]

            def _sync_fetch():
                opts = Options()
                opts.add_argument("--headless=new")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--disable-blink-features=AutomationControlled")
                opts.add_argument(f"user-agent={ua}")
                opts.add_argument("--window-size=1920,1080")
                driver = webdriver.Chrome(options=opts)
                try:
                    driver.set_page_load_timeout(20)
                    driver.get(url)
                    time.sleep(1.5)
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
                "raw_html": html,
                "word_count": int(content.get("word_count", 0)),
                "title": title or content.get("title", ""),
                "h1": content.get("h1", ""),
                "h2s": content.get("h2s", []),
                "public_emails": content.get("public_emails", []),
                "public_phones": content.get("public_phones", []),
                "social_profiles": content.get("social_profiles", []),
                "schema_persons": content.get("schema_persons", []),
                "schema_organizations": content.get("schema_organizations", []),
            }
        except Exception as e:
            logger.debug("Selenium render failed for %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # Batch crawl with cancellation check
    # ------------------------------------------------------------------
    async def crawl_urls(
        self,
        urls: List[str],
        job_id: Optional[str] = None,
        db: Optional[Any] = None,
        cancellation_check: Optional[Callable[[], Awaitable[bool]]] = None,
        is_cancelled_fn: Optional[Callable[[], Awaitable[bool]]] = None,
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        effective_max = max_pages if max_pages is not None else self.max_pages
        urls_to_crawl = urls[:effective_max]
        total = len(urls_to_crawl)
        cancel_check = is_cancelled_fn or cancellation_check

        for index, target_url in enumerate(urls_to_crawl):
            if cancel_check:
                try:
                    if await cancel_check():
                        logger.info("Cancellation detected before crawling %s", target_url)
                        break
                except Exception as ex:
                    logger.warning("Error checking cancellation: %s", ex)

            if db is not None and job_id:
                await log_job_event(
                    db, job_id, "crawling", "info", "page_crawl_started",
                    f"Fetching page {index + 1}/{total}: {target_url}",
                    url=target_url,
                    metadata={"page_index": index + 1, "total_pages": total}
                )

            page_res = await self.crawl_url(target_url)
            results.append(page_res)

            if db is not None and job_id:
                st = page_res.get("status")
                met = page_res.get("extraction_method", "httpx")
                wc = page_res.get("word_count", 0)
                lvl = "success" if st == "success" else "warning"
                msg = (
                    f"Page {index + 1}/{total} fetched via {met} ({wc} words)"
                    if st == "success"
                    else f"Page {index + 1}/{total} {st}: {page_res.get('error')}"
                )
                await log_job_event(
                    db, job_id, "crawling", lvl,
                    "page_crawl_completed" if st == "success" else "page_crawl_failed",
                    msg,
                    url=target_url,
                    metadata={
                        "page_index": index + 1,
                        "method": met,
                        "words": wc,
                        "emails_count": len(page_res.get("public_emails", [])),
                    }
                )

            if progress_callback:
                try:
                    await progress_callback(index + 1, total)
                except Exception as ex:
                    logger.debug("Progress callback failed: %s", ex)

        return results
