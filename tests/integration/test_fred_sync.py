"""Integration tests for FRED macro sync — real DB + mocked FRED API."""

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from atlas_intel.ingestion.fred_client import FREDClient
from atlas_intel.ingestion.fred_sync import sync_macro_indicators
from atlas_intel.models.macro_indicator import MacroIndicator

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fred_gdp_json():
    return json.loads((FIXTURES_DIR / "fred_gdp.json").read_text())


@pytest.fixture
def mock_fred_api(fred_gdp_json):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://api.stlouisfed.org/fred/series/observations").mock(
            return_value=Response(200, json=fred_gdp_json)
        )
        yield mock


@pytest.mark.usefixtures("mock_fred_api")
class TestFredSync:
    async def test_sync_creates_observations(self, session):
        async with FREDClient(api_key="test_key") as client:
            results = await sync_macro_indicators(session, client, ["GDP"], force=True)

        assert "GDP" in results
        assert results["GDP"] == 5  # 5 observations (including . value)

    async def test_idempotent_sync(self, session):
        async with FREDClient(api_key="test_key") as client:
            await sync_macro_indicators(session, client, ["GDP"], force=True)
            results = await sync_macro_indicators(session, client, ["GDP"], force=True)

        assert results["GDP"] == 5  # ON CONFLICT DO UPDATE

    async def test_missing_value_stored_as_null(self, session):
        async with FREDClient(api_key="test_key") as client:
            await sync_macro_indicators(session, client, ["GDP"], force=True)

        from sqlalchemy import select

        result = await session.execute(
            select(MacroIndicator)
            .where(MacroIndicator.series_id == "GDP")
            .order_by(MacroIndicator.observation_date.desc())
            .limit(1)
        )
        latest = result.scalar_one()
        # The last observation has value "." → None
        assert latest.value is None


class TestFredSyncEmpty:
    async def test_empty_response(self, session):
        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://api.stlouisfed.org/fred/series/observations").mock(
                return_value=Response(200, json={"observations": []})
            )

            async with FREDClient(api_key="test_key") as client:
                results = await sync_macro_indicators(session, client, ["EMPTY"], force=True)

        assert results["EMPTY"] == 0
