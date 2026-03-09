"""API tests for screening endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric


@pytest.fixture
async def screening_companies(session):
    """Create multiple companies with metrics for screening tests."""
    companies = []
    data = [
        ("AAPL", "Apple Inc", "Technology", "Consumer Electronics", 30.0, 45.0, 1.5, 3000e9),
        ("MSFT", "Microsoft Corp", "Technology", "Software", 35.0, 12.0, 0.4, 2800e9),
        ("JNJ", "Johnson & Johnson", "Healthcare", "Pharma", 15.0, 6.0, 0.5, 400e9),
        ("JPM", "JPMorgan Chase", "Financial Services", "Banks", 10.0, 1.5, 2.0, 450e9),
        ("XOM", "Exxon Mobil", "Energy", "Oil & Gas", 12.0, 2.0, 0.3, 350e9),
    ]

    for ticker, name, sector, industry, pe, pb, roe, mcap in data:
        c = Company(
            cik=hash(ticker) % 10000000,
            ticker=ticker,
            name=name,
            sector=sector,
            industry=industry,
        )
        session.add(c)
        await session.flush()

        session.add(
            MarketMetric(
                company_id=c.id,
                period="TTM",
                period_date=date(2024, 1, 15),
                pe_ratio=Decimal(str(pe)),
                pb_ratio=Decimal(str(pb)),
                roe=Decimal(str(roe)),
                market_cap=Decimal(str(mcap)),
                debt_to_equity=Decimal("1.0"),
                dividend_yield=Decimal("0.02"),
            )
        )
        companies.append(c)

    await session.commit()
    return companies


class TestScreeningAPI:
    async def test_screen_post_basic(self, client, session, screening_companies):
        response = await client.post(
            "/api/v1/screen",
            json={"metric_filters": [{"field": "pe_ratio", "op": "lt", "value": 20}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"] == 1
        for item in data["items"]:
            assert item["pe_ratio"] is not None
            assert item["pe_ratio"] < 20

    async def test_screen_post_multi_filter(self, client, session, screening_companies):
        response = await client.post(
            "/api/v1/screen",
            json={
                "metric_filters": [
                    {"field": "pe_ratio", "op": "lt", "value": 20},
                    {"field": "roe", "op": "gt", "value": 0.3},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"] == 2

    async def test_screen_post_sector_filter(self, client, session, screening_companies):
        response = await client.post(
            "/api/v1/screen",
            json={
                "company_filters": [{"field": "sector", "op": "eq", "value": "Technology"}],
            },
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["sector"] == "Technology"

    async def test_screen_get(self, client, session, screening_companies):
        response = await client.get("/api/v1/screen?pe_lt=20&sort_by=pe_ratio&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["pe_ratio"] is not None
            assert item["pe_ratio"] < 20

    async def test_screen_get_sector(self, client, session, screening_companies):
        response = await client.get("/api/v1/screen?sector=Healthcare")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["sector"] == "Healthcare"

    async def test_screen_empty_result(self, client, session, screening_companies):
        response = await client.post(
            "/api/v1/screen",
            json={"metric_filters": [{"field": "pe_ratio", "op": "lt", "value": 1}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    async def test_screen_no_filters(self, client, session, screening_companies):
        response = await client.post("/api/v1/screen", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5  # All companies
        assert data["filters_applied"] == 0

    async def test_screen_pagination(self, client, session, screening_companies):
        response = await client.post("/api/v1/screen", json={"limit": 2, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["limit"] == 2

    async def test_screening_stats(self, client, session, screening_companies):
        response = await client.get("/api/v1/screen/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_companies"] == 5
        assert data["companies_with_metrics"] == 5
        assert "Technology" in data["sectors"]

    async def test_screen_result_fields(self, client, session, screening_companies):
        response = await client.post("/api/v1/screen", json={"limit": 1})
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert "ticker" in item
        assert "name" in item
        assert "sector" in item
        assert "market_cap" in item
