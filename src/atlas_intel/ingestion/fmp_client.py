"""Financial Modeling Prep HTTP client with rate limiting and retries."""

import logging
from typing import Any

from atlas_intel.config import settings
from atlas_intel.ingestion.utils import BaseAPIClient

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"


class FMPClient(BaseAPIClient):
    """Async HTTP client for FMP API with rate limiting."""

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
        elif not isinstance(data, list):
            logger.warning(
                "FMP unexpected response type%s: %s",
                f" ({context})" if context else "",
                type(data).__name__,
            )
        return []

    async def get_earning_call_transcript(
        self, symbol: str, quarter: int, year: int
    ) -> list[dict[str, Any]]:
        """Fetch a specific earnings call transcript."""
        url = f"{FMP_BASE}/earning-call-transcript"
        response = await self._rate_limited_get(
            url,
            params={
                "symbol": symbol,
                "quarter": quarter,
                "year": year,
                "apikey": self._api_key,
            },
        )
        return self._ensure_list(response.json(), f"transcript {symbol} Q{quarter} {year}")

    async def get_available_transcripts(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch list of available transcript dates for a symbol."""
        url = f"{FMP_BASE}/earning-call-transcript"
        response = await self._rate_limited_get(
            url, params={"symbol": symbol, "apikey": self._api_key}
        )
        return self._ensure_list(response.json(), f"available transcripts {symbol}")

    async def get_historical_prices(
        self, symbol: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        """Fetch historical daily prices."""
        url = f"{FMP_BASE}/historical-price-eod/full"
        response = await self._rate_limited_get(
            url,
            params={
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
                "apikey": self._api_key,
            },
        )
        data: Any = response.json()
        # Stable API returns flat list; legacy wrapped in {"historical": [...]}
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            result: list[dict[str, Any]] = data.get("historical", [])
            return result
        return []

    async def get_company_profile(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch company profile data."""
        url = f"{FMP_BASE}/profile"
        response = await self._rate_limited_get(
            url, params={"symbol": symbol, "apikey": self._api_key}
        )
        return self._ensure_list(response.json(), f"profile {symbol}")

    async def get_key_metrics(
        self, symbol: str, period: str = "annual", limit: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch key financial metrics (annual or quarterly)."""
        url = f"{FMP_BASE}/key-metrics"
        response = await self._rate_limited_get(
            url,
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit,
                "apikey": self._api_key,
            },
        )
        return self._ensure_list(response.json(), f"key-metrics {symbol}")

    async def get_key_metrics_ttm(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch trailing twelve month key metrics."""
        url = f"{FMP_BASE}/key-metrics-ttm"
        response = await self._rate_limited_get(
            url, params={"symbol": symbol, "apikey": self._api_key}
        )
        return self._ensure_list(response.json(), f"key-metrics-ttm {symbol}")

    async def get_ratios(
        self, symbol: str, period: str = "annual", limit: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch financial ratios (annual or quarterly)."""
        url = f"{FMP_BASE}/ratios"
        response = await self._rate_limited_get(
            url,
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit,
                "apikey": self._api_key,
            },
        )
        return self._ensure_list(response.json(), f"ratios {symbol}")

    async def get_ratios_ttm(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch trailing twelve month financial ratios."""
        url = f"{FMP_BASE}/ratios-ttm"
        response = await self._rate_limited_get(
            url, params={"symbol": symbol, "apikey": self._api_key}
        )
        return self._ensure_list(response.json(), f"ratios-ttm {symbol}")

    async def get_stock_news(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch stock news articles."""
        url = f"{FMP_BASE}/news/stock"
        response = await self._rate_limited_get(
            url,
            params={"symbols": symbol, "limit": limit, "apikey": self._api_key},
        )
        return self._ensure_list(response.json(), f"news {symbol}")

    async def get_insider_trading(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch insider trading transactions."""
        url = f"{FMP_BASE}/insider-trading"
        response = await self._rate_limited_get(
            url,
            params={"symbol": symbol, "limit": limit, "apikey": self._api_key},
        )
        return self._ensure_list(response.json(), f"insider-trading {symbol}")

    async def get_analyst_estimates(
        self, symbol: str, period: str = "annual", limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch analyst consensus estimates."""
        url = f"{FMP_BASE}/analyst-estimates"
        response = await self._rate_limited_get(
            url,
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit,
                "apikey": self._api_key,
            },
        )
        return self._ensure_list(response.json(), f"analyst-estimates {symbol}")

    async def get_price_target_consensus(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch price target consensus."""
        url = f"{FMP_BASE}/price-target-consensus"
        response = await self._rate_limited_get(
            url, params={"symbol": symbol, "apikey": self._api_key}
        )
        return self._ensure_list(response.json(), f"price-target {symbol}")

    async def get_analyst_grades(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch analyst grades (upgrades/downgrades)."""
        url = f"{FMP_BASE}/grades"
        response = await self._rate_limited_get(
            url,
            params={"symbol": symbol, "limit": limit, "apikey": self._api_key},
        )
        return self._ensure_list(response.json(), f"grades {symbol}")

    async def get_institutional_holders(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch institutional ownership data."""
        url = f"{FMP_BASE}/institutional-ownership/symbol"
        response = await self._rate_limited_get(
            url,
            params={"symbol": symbol, "limit": limit, "apikey": self._api_key},
        )
        return self._ensure_list(response.json(), f"institutional {symbol}")
