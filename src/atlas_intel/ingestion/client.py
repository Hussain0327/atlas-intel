"""SEC EDGAR HTTP client with rate limiting and retries."""

import asyncio
import logging
import time
from typing import Any

import httpx

from atlas_intel.config import settings

logger = logging.getLogger(__name__)

SEC_BASE = "https://data.sec.gov"
SEC_EFTS = "https://efts.sec.gov"
SEC_WWW = "https://www.sec.gov"


class SECClient:
    """Async HTTP client for SEC EDGAR API with rate limiting."""

    def __init__(
        self,
        rate_limit: int = settings.sec_rate_limit,
        user_agent: str = settings.sec_user_agent,
    ):
        self._rate_limit = rate_limit
        self._semaphore = asyncio.Semaphore(rate_limit)
        self._min_interval = 1.0 / rate_limit
        self._last_request_time = 0.0
        self._client = httpx.AsyncClient(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
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
                            "SEC API %s (attempt %d/%d), retrying in %ds",
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

    async def get_company_tickers(self) -> dict[str, Any]:
        """Fetch CIK-ticker mapping from SEC."""
        url = f"{SEC_WWW}/files/company_tickers.json"
        response = await self._rate_limited_get(url)
        data: dict[str, Any] = response.json()
        return data

    async def get_submissions(self, cik: int) -> dict[str, Any]:
        """Fetch filing submissions for a company by CIK."""
        padded = str(cik).zfill(10)
        url = f"{SEC_BASE}/submissions/CIK{padded}.json"
        response = await self._rate_limited_get(url)
        data: dict[str, Any] = response.json()
        return data

    async def get_company_facts(self, cik: int) -> dict[str, Any]:
        """Fetch XBRL company facts for a company by CIK."""
        padded = str(cik).zfill(10)
        url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{padded}.json"
        response = await self._rate_limited_get(url)
        data: dict[str, Any] = response.json()
        return data

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "SECClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
