"""
CMS detection and public REST API discovery (WordPress, etc.).
Strictly accesses only public endpoints without bypassing authentication.
"""
import logging
from typing import List, Dict, Optional, Any
import httpx
from bs4 import BeautifulSoup
from app.utils.ssrf_guard import is_safe_url

logger = logging.getLogger(__name__)

class CMSDiscovery:
    async def detect_cms(self, base_url: str, html: Optional[str] = None) -> Optional[str]:
        """Detect CMS from headers, generator tags, and well-known paths."""
        safe, reason = is_safe_url(base_url)
        if not safe:
            return None

        # Check HTML meta generator
        if html:
            soup = BeautifulSoup(html, "html.parser")
            meta = soup.find("meta", attrs={"name": "generator"})
            if meta and meta.get("content"):
                gen = meta["content"].lower()
                if "wordpress" in gen:
                    return "wordpress"
                if "drupal" in gen:
                    return "drupal"
                if "joomla" in gen:
                    return "joomla"
                if "ghost" in gen:
                    return "ghost"

        # Check /wp-json/ endpoint
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/wp-json/")
                if resp.status_code == 200 and "namespaces" in resp.text:
                    return "wordpress"
        except Exception:
            pass

        return None

    async def discover_wordpress_urls(self, base_url: str, max_items: int = 100) -> List[Dict[str, Any]]:
        """Query public WordPress REST API for published posts and pages."""
        safe, _ = is_safe_url(base_url)
        if not safe:
            return []

        discovered: List[Dict[str, Any]] = []
        endpoints = ["/wp-json/wp/v2/pages", "/wp-json/wp/v2/posts"]

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for ep in endpoints:
                page = 1
                while len(discovered) < max_items:
                    url = f"{base_url.rstrip('/')}{ep}"
                    try:
                        resp = await client.get(url, params={"per_page": 50, "page": page, "_fields": "id,link,title,date,slug"})
                        if resp.status_code != 200:
                            break
                        items = resp.json()
                        if not items or not isinstance(items, list):
                            break

                        for item in items:
                            link = item.get("link")
                            title_obj = item.get("title", {})
                            title = title_obj.get("rendered") if isinstance(title_obj, dict) else str(title_obj)
                            if link:
                                discovered.append({
                                    "url": link,
                                    "title": title or "",
                                    "published_at": item.get("date"),
                                    "source": "wordpress_api",
                                })

                        page += 1
                        if len(items) < 50:
                            break
                    except Exception as e:
                        logger.debug(f"WP API query failed on {url}: {e}")
                        break

        return discovered
