"""SEC EDGAR HTTP client with rate limiting and retries."""

import logging
from typing import Any

from atlas_intel.config import settings
from atlas_intel.ingestion.utils import BaseAPIClient

logger = logging.getLogger(__name__)

SEC_BASE = "https://data.sec.gov"
SEC_EFTS = "https://efts.sec.gov"
SEC_WWW = "https://www.sec.gov"


class SECClient(BaseAPIClient):
    """Async HTTP client for SEC EDGAR API with rate limiting."""

    def __init__(
        self,
        rate_limit: int = settings.sec_rate_limit,
        user_agent: str = settings.sec_user_agent,
    ):
        super().__init__(
            rate_limit=rate_limit,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )

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
