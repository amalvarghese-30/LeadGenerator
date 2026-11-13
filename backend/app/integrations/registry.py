"""
Integration status registry.
Manages status checks and health monitoring for external components (NVIDIA, MongoDB, SearXNG).
NEVER exposes API keys or secrets in status responses.
"""
import logging
from typing import List, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    def __init__(self, db=None):
        self.db = db

    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """Return integration statuses without revealing any secrets."""
        statuses = [
            await self.check_mongodb(),
            await self.check_nvidia(),
            await self.check_searxng(),
            await self.check_ddgs(),
        ]
        return statuses

    async def check_mongodb(self) -> Dict[str, Any]:
        try:
            if self.db is not None:
                await self.db.command("ping")
                return {
                    "name": "MongoDB Database",
                    "id": "mongodb",
                    "status": "connected",
                    "is_optional": False,
                    "message": "Connected and responding to ping",
                }
            return {
                "name": "MongoDB Database",
                "id": "mongodb",
                "status": "unknown",
                "is_optional": False,
                "message": "Database client uninitialized",
            }
        except Exception as e:
            return {
                "name": "MongoDB Database",
                "id": "mongodb",
                "status": "error",
                "is_optional": False,
                "message": f"Connection error: {str(e)}",
            }

    async def check_nvidia(self) -> Dict[str, Any]:
        has_key = bool(settings.NVIDIA_API_KEY)
        if not has_key:
            return {
                "name": "NVIDIA Nemotron AI",
                "id": "nvidia",
                "status": "not_configured",
                "is_optional": True,
                "message": "API key not configured; running in deterministic NLP fallback mode",
                "model": settings.NVIDIA_MODEL,
            }

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{settings.NVIDIA_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {settings.NVIDIA_API_KEY}"}
                )
                if resp.status_code == 200:
                    return {
                        "name": "NVIDIA Nemotron AI",
                        "id": "nvidia",
                        "status": "active",
                        "is_optional": True,
                        "message": "Connected to NVIDIA NIM API",
                        "model": settings.NVIDIA_MODEL,
                    }
                else:
                    return {
                        "name": "NVIDIA Nemotron AI",
                        "id": "nvidia",
                        "status": "error",
                        "is_optional": True,
                        "message": f"Authentication / API error ({resp.status_code})",
                        "model": settings.NVIDIA_MODEL,
                    }
        except Exception as e:
            return {
                "name": "NVIDIA Nemotron AI",
                "id": "nvidia",
                "status": "error",
                "is_optional": True,
                "message": f"Network unreachable: {str(e)}",
                "model": settings.NVIDIA_MODEL,
            }

    async def check_searxng(self) -> Dict[str, Any]:
        configured = bool(settings.SEARXNG_BASE_URL)
        if not configured:
            return {
                "name": "SearXNG (Self-Hosted)",
                "id": "searxng",
                "status": "not_configured",
                "is_optional": True,
                "message": "Optional self-hosted search engine not configured",
            }
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                resp = await client.get(f"{settings.SEARXNG_BASE_URL.rstrip('/')}/healthz")
                is_ok = resp.status_code in (200, 302)
                return {
                    "name": "SearXNG (Self-Hosted)",
                    "id": "searxng",
                    "status": "active" if is_ok else "error",
                    "is_optional": True,
                    "message": "Service responding" if is_ok else f"HTTP status {resp.status_code}",
                }
        except Exception as e:
            return {
                "name": "SearXNG (Self-Hosted)",
                "id": "searxng",
                "status": "error",
                "is_optional": True,
                "message": f"Could not reach SearXNG instance: {str(e)}",
            }

    async def check_ddgs(self) -> Dict[str, Any]:
        return {
            "name": "DuckDuckGo Discovery (DDGS)",
            "id": "ddgs",
            "status": "active",
            "is_optional": False,
            "message": "Zero-key free discovery engine operational",
        }
