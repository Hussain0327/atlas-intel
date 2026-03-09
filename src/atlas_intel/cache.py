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
            return cached  # type: ignore[return-value]

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
