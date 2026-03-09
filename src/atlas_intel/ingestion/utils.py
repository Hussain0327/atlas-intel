"""Shared ingestion utilities: datetime helpers and base HTTP client."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any, Self

import httpx

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """Return current naive UTC datetime (for use with naive DateTime columns)."""
    return datetime.now(UTC).replace(tzinfo=None)


class BaseAPIClient:
    """Async HTTP client base with rate limiting and exponential backoff retries."""

    def __init__(
        self,
        rate_limit: int,
        headers: dict[str, str] | None = None,
    ):
        self._rate_limit = rate_limit
        self._semaphore = asyncio.Semaphore(rate_limit)
        self._rate_limit_lock = asyncio.Lock()
        self._min_interval = 1.0 / rate_limit
        self._last_request_time = 0.0
        self._client = httpx.AsyncClient(
            headers=headers or {},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def _rate_limited_get(
        self,
        url: str,
        max_retries: int = 3,
        params: dict[str, Any] | None = None,
        raise_on_error: bool = True,
    ) -> httpx.Response:
        async with self._semaphore:
            async with self._rate_limit_lock:
                now = time.monotonic()
                elapsed = now - self._last_request_time
                if elapsed < self._min_interval:
                    await asyncio.sleep(self._min_interval - elapsed)
                self._last_request_time = time.monotonic()

            for attempt in range(max_retries):
                try:
                    response = await self._client.get(url, params=params)
                    if response.status_code == 429 or response.status_code >= 500:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "API %s (attempt %d/%d), retrying in %ds",
                            response.status_code,
                            attempt + 1,
                            max_retries,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    if raise_on_error:
                        response.raise_for_status()
                    return response
                except httpx.HTTPStatusError:
                    raise
                except httpx.HTTPError as e:
                    if attempt == max_retries - 1:
                        raise
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "HTTP error %s (attempt %d/%d), retrying in %ds",
                        e,
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)

            raise httpx.HTTPError(f"Failed after {max_retries} retries: {url}")

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
