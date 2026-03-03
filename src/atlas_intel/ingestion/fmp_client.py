"""Financial Modeling Prep HTTP client with rate limiting and retries."""

import asyncio
import logging
import time
from typing import Any

import httpx

from atlas_intel.config import settings

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v3"


class FMPClient:
    """Async HTTP client for FMP API with rate limiting."""

    def __init__(
        self,
        api_key: str = settings.fmp_api_key,
        rate_limit: int = settings.fmp_rate_limit,
    ):
        self._api_key = api_key
        self._rate_limit = rate_limit
        self._semaphore = asyncio.Semaphore(rate_limit)
        self._min_interval = 1.0 / rate_limit
        self._last_request_time = 0.0
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def _rate_limited_get(self, url: str, max_retries: int = 3) -> httpx.Response:
        async with self._semaphore:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

            for attempt in range(max_retries):
                try:
                    response = await self._client.get(url)
                    if response.status_code == 429 or response.status_code >= 500:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "FMP API %s (attempt %d/%d), retrying in %ds",
                            response.status_code,
                            attempt + 1,
                            max_retries,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
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

    async def get_earning_call_transcript(
        self, symbol: str, quarter: int, year: int
    ) -> list[dict[str, Any]]:
        """Fetch a specific earnings call transcript."""
        url = (
            f"{FMP_BASE}/earning_call_transcript/{symbol}"
            f"?quarter={quarter}&year={year}&apikey={self._api_key}"
        )
        response = await self._rate_limited_get(url)
        data: list[dict[str, Any]] = response.json()
        return data

    async def get_available_transcripts(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch list of available transcript dates for a symbol."""
        url = f"{FMP_BASE}/earning_call_transcript?symbol={symbol}&apikey={self._api_key}"
        response = await self._rate_limited_get(url)
        data: list[dict[str, Any]] = response.json()
        return data

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "FMPClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
