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

    async def get_8k_filings(
        self,
        cik: int,
        start_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract 8-K filings from submissions data.

        Uses the existing submissions endpoint and filters for 8-K forms.
        Returns a list of filing dicts with form, filingDate, accessionNumber, items.
        """
        submissions = await self.get_submissions(cik)
        recent = submissions.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        items_list = recent.get("items", [""] * len(forms))
        descs = recent.get("primaryDocDescription", [""] * len(forms))

        results: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form != "8-K":
                continue
            filing_date = dates[i] if i < len(dates) else ""
            if start_date and filing_date < start_date:
                continue
            results.append(
                {
                    "form": form,
                    "filingDate": filing_date,
                    "accessionNumber": accessions[i] if i < len(accessions) else "",
                    "items": items_list[i] if i < len(items_list) else "",
                    "description": descs[i] if i < len(descs) else "",
                }
            )
        return results
