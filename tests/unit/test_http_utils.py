"""Unit tests for HTTP utility behavior."""

import asyncio
import time
from itertools import pairwise
from unittest.mock import AsyncMock

import pytest
from httpx import Request, Response

from atlas_intel.ingestion.utils import BaseAPIClient


class TestBaseAPIClientRateLimiting:
    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_min_interval(self):
        client = BaseAPIClient(rate_limit=50)
        request_times: list[float] = []

        async def fake_get(url, params=None):
            request_times.append(time.monotonic())
            return Response(200, json={"ok": True}, request=Request("GET", url))

        client._client.get = AsyncMock(side_effect=fake_get)
        try:
            await asyncio.gather(
                client._rate_limited_get("https://example.com/1"),
                client._rate_limited_get("https://example.com/2"),
                client._rate_limited_get("https://example.com/3"),
            )
        finally:
            await client.close()

        gaps = [b - a for a, b in pairwise(request_times)]
        assert len(request_times) == 3
        assert gaps
        assert min(gaps) >= 0.015
