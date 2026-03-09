"""USPTO PatentsView HTTP client."""

import json
import logging
from typing import Any

from atlas_intel.config import settings
from atlas_intel.ingestion.utils import BaseAPIClient

logger = logging.getLogger(__name__)

PATENT_BASE = "https://search.patentsview.org/api/v1"


class PatentClient(BaseAPIClient):
    """Async HTTP client for USPTO PatentsView API."""

    def __init__(
        self,
        api_key: str = settings.patent_api_key,
        rate_limit: int = settings.patent_rate_limit,
    ):
        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["X-Api-Key"] = api_key
        self._has_key = bool(api_key)
        super().__init__(rate_limit=rate_limit, headers=headers)

    async def search_patents(
        self,
        assignee_name: str,
        after_date: str | None = None,
    ) -> dict[str, Any]:
        """Search patents by assignee organization name."""
        if not self._has_key:
            logger.warning("No PATENT_API_KEY configured — skipping PatentsView query")
            return {"patents": []}

        url = f"{PATENT_BASE}/patent/"
        q: dict[str, Any] = {"_contains": {"assignees.assignee_organization": assignee_name}}
        if after_date:
            q["_gte"] = {"patent_date": after_date}

        fields = json.dumps(
            [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_type",
                "patent_abstract",
                "patent_num_us_patent_citations",
                "assignees.assignee_organization",
                "cpcs.cpc_group_id",
                "application.filing_date",
            ]
        )
        params: dict[str, str] = {
            "q": json.dumps(q),
            "f": fields,
            "o": json.dumps({"size": 100}),
        }
        response = await self._rate_limited_get(url, params=params)
        data: dict[str, Any] = response.json()
        return data
