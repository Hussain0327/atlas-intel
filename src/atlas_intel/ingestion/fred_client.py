"""FRED (Federal Reserve Economic Data) HTTP client."""

import logging
from typing import Any

from atlas_intel.config import settings
from atlas_intel.ingestion.utils import BaseAPIClient

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"


class FREDClient(BaseAPIClient):
    """Async HTTP client for FRED API with rate limiting."""

    def __init__(
        self,
        api_key: str = settings.fred_api_key,
        rate_limit: int = settings.fred_rate_limit,
    ):
        self._api_key = api_key
        super().__init__(
            rate_limit=rate_limit,
            headers={"Accept-Encoding": "gzip, deflate"},
        )

    async def get_series_observations(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch observations for a FRED series."""
        url = f"{FRED_BASE}/series/observations"
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date
        response = await self._rate_limited_get(url, params=params)
        data: dict[str, Any] = response.json()
        return data
