"""Congress trading data client (via FMP senate/house trading endpoints)."""

import logging
from typing import Any

from atlas_intel.config import settings
from atlas_intel.ingestion.utils import BaseAPIClient

logger = logging.getLogger(__name__)

FMP_STABLE = "https://financialmodelingprep.com/stable"
FMP_V4 = "https://financialmodelingprep.com/api/v4"


class CongressClient(BaseAPIClient):
    """Async HTTP client for congressional trading data via FMP."""

    def __init__(
        self,
        api_key: str = settings.fmp_api_key,
        rate_limit: int = settings.fmp_rate_limit,
    ):
        self._api_key = api_key
        super().__init__(
            rate_limit=rate_limit,
            headers={"User-Agent": "AtlasIntel", "Accept-Encoding": "gzip, deflate"},
        )

    @staticmethod
    def _ensure_list(data: Any, context: str = "") -> list[dict[str, Any]]:
        """Validate that API response is a list, returning [] for error dicts."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "Error Message" in data:
            logger.warning("FMP API error%s: %s", f" ({context})" if context else "", data)
        return []

    async def _get_with_fallback(
        self, endpoint: str, symbol: str, limit: int
    ) -> list[dict[str, Any]]:
        """Try /stable/ first, fall back to /api/v4/ on 404."""
        params: dict[str, Any] = {"symbol": symbol, "limit": limit, "apikey": self._api_key}

        for base in (FMP_STABLE, FMP_V4):
            url = f"{base}/{endpoint}"
            response = await self._rate_limited_get(url, params=params, raise_on_error=False)
            if response.status_code in (403, 404):
                continue
            response.raise_for_status()
            return self._ensure_list(response.json(), f"{endpoint} {symbol}")

        logger.warning(
            "Congress endpoint %s unavailable for %s (plan restriction)",
            endpoint,
            symbol,
        )
        return []

    async def get_senate_trading(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch senate trading disclosures for a symbol."""
        return await self._get_with_fallback("senate-trading", symbol, limit)

    async def get_house_trading(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch house trading disclosures for a symbol."""
        return await self._get_with_fallback("house-disclosure", symbol, limit)
