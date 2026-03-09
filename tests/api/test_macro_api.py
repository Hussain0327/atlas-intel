"""API tests for macro indicator endpoints."""

import pytest

from atlas_intel.models.macro_indicator import MacroIndicator


@pytest.fixture
async def seed_macro(session):
    """Seed macro indicators directly."""
    from datetime import date
    from decimal import Decimal

    indicators = [
        MacroIndicator(
            series_id="GDP",
            observation_date=date(2024, 1, 1),
            value=Decimal("27956.998"),
        ),
        MacroIndicator(
            series_id="GDP",
            observation_date=date(2024, 4, 1),
            value=Decimal("28628.121"),
        ),
        MacroIndicator(
            series_id="UNRATE",
            observation_date=date(2024, 1, 1),
            value=Decimal("3.7"),
        ),
    ]
    session.add_all(indicators)
    await session.commit()


class TestMacroAPI:
    async def test_list_indicators(self, client, session, seed_macro):
        response = await client.get("/api/v1/macro/indicators")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_filter_by_series(self, client, session, seed_macro):
        response = await client.get("/api/v1/macro/indicators?series_id=GDP")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["series_id"] == "GDP"

    async def test_summary(self, client, session, seed_macro):
        response = await client.get("/api/v1/macro/summary")
        assert response.status_code == 200
        data = response.json()
        assert len(data["series"]) == 2  # GDP and UNRATE
