"""API tests for price endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.stock_price import StockPrice


@pytest.fixture
async def seeded_prices(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    prices = [
        StockPrice(
            company_id=company.id,
            price_date=date(2024, 1, 22),
            open=Decimal("193.71"),
            high=Decimal("195.33"),
            low=Decimal("193.53"),
            close=Decimal("193.89"),
            adj_close=Decimal("193.89"),
            volume=56735102,
        ),
        StockPrice(
            company_id=company.id,
            price_date=date(2024, 1, 23),
            open=Decimal("195.18"),
            high=Decimal("195.33"),
            low=Decimal("193.81"),
            close=Decimal("195.18"),
            adj_close=Decimal("195.18"),
            volume=42247609,
        ),
        StockPrice(
            company_id=company.id,
            price_date=date(2024, 1, 24),
            open=Decimal("195.42"),
            high=Decimal("196.38"),
            low=Decimal("194.34"),
            close=Decimal("194.50"),
            adj_close=Decimal("194.50"),
            volume=53609374,
        ),
        StockPrice(
            company_id=company.id,
            price_date=date(2024, 1, 25),
            open=Decimal("195.22"),
            high=Decimal("196.38"),
            low=Decimal("193.81"),
            close=Decimal("194.17"),
            adj_close=Decimal("194.17"),
            volume=54148506,
        ),
        StockPrice(
            company_id=company.id,
            price_date=date(2024, 1, 26),
            open=Decimal("194.27"),
            high=Decimal("196.17"),
            low=Decimal("193.82"),
            close=Decimal("192.42"),
            adj_close=Decimal("192.42"),
            volume=44587041,
        ),
    ]
    session.add_all(prices)
    await session.commit()
    return company


class TestPricesAPI:
    async def test_list_prices(self, client, seeded_prices):
        resp = await client.get("/api/v1/companies/AAPL/prices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    async def test_date_range_filter(self, client, seeded_prices):
        resp = await client.get(
            "/api/v1/companies/AAPL/prices",
            params={"from": "2024-01-24", "to": "2024-01-25"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_analytics_endpoint(self, client, seeded_prices):
        resp = await client.get("/api/v1/companies/AAPL/prices/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["latest_close"] is not None
        assert data["latest_date"] == "2024-01-26"

    async def test_returns_endpoint(self, client, seeded_prices):
        resp = await client.get("/api/v1/companies/AAPL/prices/returns")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert "daily_return" in data[0]

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/prices")
        assert resp.status_code == 404

    async def test_pagination(self, client, seeded_prices):
        resp = await client.get("/api/v1/companies/AAPL/prices", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
