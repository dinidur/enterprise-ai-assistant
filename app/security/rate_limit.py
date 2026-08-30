"""Per-user token bucket rate limiting.

Token bucket is required by the assessment and is the right shape for chat
traffic: it allows a short burst - a user asking three quick follow-ups - while
still bounding sustained load, which a fixed window does badly.

Each user gets an independent bucket. Refill is computed lazily from elapsed
time rather than by a background task, so there is no timer to supervise and an
idle process costs nothing.

Buckets live in process memory. That is correct for a single-instance POC and
wrong for a horizontally scaled deployment, where the counter must be shared -
Redis with the same algorithm is the documented next step.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class Bucket:
    """One user's bucket."""

    capacity: float
    refill_per_second: float
    tokens: float = field(init=False)
    updated_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now

    def take(self, cost: float = 1.0) -> tuple[bool, float]:
        """Try to spend tokens. Returns ``(allowed, retry_after_seconds)``."""
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return True, 0.0
        deficit = cost - self.tokens
        return False, deficit / self.refill_per_second


class RateLimiter:
    """Thread-safe registry of per-user buckets."""

    def __init__(self, capacity: int | None = None, refill_per_second: float | None = None) -> None:
        self._capacity = float(capacity or settings.rate_limit_capacity)
        self._refill = float(refill_per_second or settings.rate_limit_refill_per_second)
        self._buckets: dict[str, Bucket] = {}
        self._lock = asyncio.Lock()

    async def check(self, user_id: str, cost: float = 1.0) -> None:
        """Consume one token for the user, or raise.

        Raises:
            RateLimitExceeded: with the retry delay in the message.
        """
        async with self._lock:
            bucket = self._buckets.get(user_id)
            if bucket is None:
                bucket = Bucket(capacity=self._capacity, refill_per_second=self._refill)
                self._buckets[user_id] = bucket
            allowed, retry_after = bucket.take(cost)

        if not allowed:
            log.warning("rate_limit_exceeded", user_id=user_id, retry_after=round(retry_after, 1))
            raise RateLimitExceeded(
                f"Rate limit exceeded. Try again in {retry_after:.0f} seconds."
            )

    async def remaining(self, user_id: str) -> float:
        """Tokens left, for the UI to display."""
        async with self._lock:
            bucket = self._buckets.get(user_id)
            if bucket is None:
                return self._capacity
            bucket._refill()
            return round(bucket.tokens, 1)


limiter = RateLimiter()
