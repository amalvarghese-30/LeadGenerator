import asyncio
import time
from collections import defaultdict, deque
from typing import Dict


class AsyncRateLimiter:
    """
    Simple in-process async token-bucket rate limiter.
    Not suitable for multi-process deployments; use Redis for that.
    """

    def __init__(self, rate: int = 60, period: float = 60.0, burst: int = 10):
        """
        rate: max requests per `period` seconds.
        burst: max concurrent requests above the sustained rate.
        """
        self._rate = rate
        self._period = period
        self._burst = burst
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._windows: Dict[str, deque] = defaultdict(deque)

    def _is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        window = self._windows[key]
        # Remove timestamps outside the window
        while window and now - window[0] > self._period:
            window.popleft()
        if len(window) < self._rate + self._burst:
            window.append(now)
            return True
        return False

    async def acquire(self, key: str) -> bool:
        """Returns True if request is within rate limit, False otherwise."""
        async with self._locks[key]:
            return self._is_allowed(key)

    async def wait_or_raise(self, key: str, timeout: float = 5.0) -> None:
        """Wait until rate limit allows, or raise RuntimeError on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            if await self.acquire(key):
                return
            if time.monotonic() > deadline:
                raise RuntimeError(f"Rate limit exceeded for key: {key!r}")
            await asyncio.sleep(0.1)


# Default global limiter
default_limiter = AsyncRateLimiter(rate=100, period=60.0, burst=20)
