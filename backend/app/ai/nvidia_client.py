"""
NVIDIA Nemotron API client.

Design principles:
- Gracefully disabled when NVIDIA_API_KEY is not configured; callers
  should always check is_available() or handle None returns.
- API key is NEVER logged, returned, or included in error messages.
- All AI output passes through OutputValidator before being returned;
  nothing is returned raw.
- verification_status is always "pending" — AI cannot self-verify.
"""
import logging
from typing import Dict, List, Optional

import httpx

from app.ai.output_validator import OutputValidator
from app.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy settings import so the module can be imported without a full app context
# (e.g. during unit tests that mock settings).
# ---------------------------------------------------------------------------
def _get_settings():
    from app.config import settings  # noqa: PLC0415
    return settings


class NvidiaClient:
    """
    Thin async wrapper around the NVIDIA NIM / Nemotron chat-completions API.

    Usage::

        client = NvidiaClient()
        if await client.is_available():
            entities = await client.extract_entities(text, url)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Parameters can be injected directly (useful in tests).
        When omitted, values are read from app settings.
        """
        cfg = _get_settings()
        # Use injected values first, then fall back to config
        self._api_key: str = api_key or getattr(cfg, "NVIDIA_API_KEY", "") or ""
        self.base_url: str = (base_url or getattr(cfg, "NVIDIA_BASE_URL", getattr(cfg, "NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")) or "https://integrate.api.nvidia.com/v1").rstrip("/")
        self.model: str = model or getattr(cfg, "NVIDIA_MODEL", "meta/llama-3.1-70b-instruct") or "meta/llama-3.1-70b-instruct"

        # Public flag — no secret exposed
        self.available: bool = bool(self._api_key)

        self.prompt_builder = PromptBuilder()
        self.validator = OutputValidator()

        if not self.available:
            logger.info(
                "NVIDIA API key not configured — operating in NLP-only mode"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_available(self) -> bool:
        """
        Returns True only if the API key is set AND the API endpoint responds
        with HTTP 200 to a lightweight probe.
        """
        if not self.available:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._auth_headers(),
                )
                return resp.status_code == 200
        except Exception:
            # Network errors, DNS failures etc. — treat as unavailable
            return False

    async def extract_entities(
        self,
        page_text: str,
        source_url: str,
        page_title: str = "",
    ) -> Optional[List[Dict]]:
        """
        Extract client relationship entities from a crawled page.

        Returns:
            List of validated entity dicts (all with verification_status="pending"),
            or None if the client is unavailable, the API errors, or no valid
            entities are found after validation.
        """
        if not self.available:
            return None

        prompt = self.prompt_builder.build_extraction_prompt(
            page_text, source_url, page_title
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user",   "content": prompt["user"]},
            ],
            "max_tokens": 2048,
            "temperature": 0.1,         # Low temperature → factual, deterministic
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={**self._auth_headers(), "Content-Type": "application/json"},
                )

            if resp.status_code != 200:
                # Log only status + first 200 chars of body — never log the key
                logger.warning(
                    "NVIDIA API returned %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None

            data = resp.json()
            raw_content: str = data["choices"][0]["message"]["content"]

            # Validate before returning — never trust raw AI output
            return self.validator.validate_extraction_output(raw_content, source_url)

        except httpx.TimeoutException:
            logger.warning("NVIDIA API timed out for %s", source_url)
            return None
        except KeyError as exc:
            logger.warning("Unexpected NVIDIA API response structure: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("NVIDIA API error for %s: %s", source_url, exc)
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        """Return Authorization header dict. Never logs the key."""
        return {"Authorization": f"Bearer {self._api_key}"}
