"""Simple in-memory TTL cache for hot read paths."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()
        self._key_locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> object | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None

            expires_at, value = entry
            if expires_at <= time.monotonic():
                self._entries.pop(key, None)
                return None

            return deepcopy(value)

    async def set(self, key: str, value: object, ttl_seconds: int) -> None:
        async with self._lock:
            self._entries[key] = (time.monotonic() + ttl_seconds, deepcopy(value))

    async def get_or_set(
        self,
        key: str,
        ttl_seconds: int,
        loader: Callable[[], Awaitable[T]],
    ) -> T:
        cached = await self.get(key)
        if cached is not None:
            _record_cache_hit(key)
            return cached  # type: ignore[return-value]

        # Get or create per-key lock to prevent thundering herd
        async with self._lock:
            if key not in self._key_locks:
                self._key_locks[key] = asyncio.Lock()
            key_lock = self._key_locks[key]

        async with key_lock:
            # Double-check after acquiring lock
            cached = await self.get(key)
            if cached is not None:
                _record_cache_hit(key)
                return cached  # type: ignore[return-value]
            _record_cache_miss(key)
            value = await loader()
            await self.set(key, value, ttl_seconds)
            return value

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._entries.pop(key, None)

    async def invalidate_prefix(self, prefix: str) -> None:
        async with self._lock:
            for key in [k for k in self._entries if k.startswith(prefix)]:
                self._entries.pop(key, None)


read_cache = TTLCache()


def _record_cache_hit(key: str) -> None:
    try:
        from atlas_intel.metrics import cache_hits_total

        cache_name = key.split(":")[0] if ":" in key else "default"
        cache_hits_total.labels(cache_name=cache_name).inc()
    except Exception:
        pass


def _record_cache_miss(key: str) -> None:
    try:
        from atlas_intel.metrics import cache_misses_total

        cache_name = key.split(":")[0] if ":" in key else "default"
        cache_misses_total.labels(cache_name=cache_name).inc()
    except Exception:
        pass
