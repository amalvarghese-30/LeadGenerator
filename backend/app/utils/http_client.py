"""
Unified HTTP Client Utility with Anti-Cloudflare & Anti-Bot Stealth Headers.
Provides rotating realistic Chrome/Edge browser headers, HTTP/2 support,
and Cloudflare/WAF challenge detection.
"""
import random
from typing import Dict, Optional, Tuple
import httpx

try:
    import h2  # noqa: F401
    HAS_HTTP2 = True
except ImportError:
    HAS_HTTP2 = False

CHROME_PROFILES = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"macOS"',
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
        "sec_ch_ua": '"Chromium";v="126", "Microsoft Edge";v="126", "Not-A.Brand";v="99"',
        "platform": '"Windows"',
    },
]

CLOUDFLARE_INDICATORS = [
    "cf-browser-verification",
    "cf-challenge",
    "just a moment...",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "please turn javascript on and reload",
    "challenges.cloudflare.com",
    "turnstile",
    "access denied",
    "ddos protection by cloudflare",
    "security check to access",
    "waf_challenge",
    "incident id",
]

def get_stealth_headers(url: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, str]:
    """
    Returns high-fidelity browser headers indistinguishable from a real desktop user.
    """
    profile = random.choice(CHROME_PROFILES)
    headers = {
        "User-Agent": profile["user_agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": profile["sec_ch_ua"],
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": profile["platform"],
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site" if referer else "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers

def is_cloudflare_or_blocked(status_code: int, html_body: str) -> Tuple[bool, str]:
    """
    Analyzes response status and body to detect Cloudflare, Akamai, Datadome,
    or generic anti-bot challenge / blocking pages.
    """
    if status_code in (403, 429, 503):
        return True, f"HTTP_{status_code}_STATUS_BLOCK"

    lower_body = (html_body or "")[:5000].lower()
    for indicator in CLOUDFLARE_INDICATORS:
        if indicator in lower_body:
            return True, f"BOT_CHALLENGE_FOUND:{indicator}"

    # Empty SPA shell check (< 250 characters with no real body content)
    clean_body = lower_body.strip()
    if len(clean_body) < 250 and ("<div id=\"root\"></div>" in clean_body or "<div id=\"app\"></div>" in clean_body or not clean_body):
        return True, "EMPTY_SPA_SHELL"

    return False, "OK"

def create_stealth_client(timeout: float = 15.0, **kwargs) -> httpx.AsyncClient:
    """
    Factory for httpx.AsyncClient pre-configured with realistic settings,
    redirects, and stealth headers.
    """
    headers = kwargs.pop("headers", None) or get_stealth_headers()
    http2 = kwargs.pop("http2", HAS_HTTP2)
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        follow_redirects=True,
        http2=http2,
        **kwargs
    )
