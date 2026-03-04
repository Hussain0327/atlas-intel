"""API tests for market metrics endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric


@pytest.fixture
async def seeded_metrics(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.", sector="Technology")
    session.add(company)
    await session.flush()

    company2 = Company(cik=789019, ticker="MSFT", name="Microsoft Corp", sector="Technology")
    session.add(company2)
    await session.flush()

    metrics = [
        MarketMetric(
            company_id=company.id,
            period="TTM",
            period_date=date(2024, 1, 26),
            pe_ratio=Decimal("30.82"),
            pb_ratio=Decimal("47.89"),
            market_cap=Decimal("2987123456789"),
            roe=Decimal("1.51"),
            debt_to_equity=Decimal("1.79"),
        ),
        MarketMetric(
            company_id=company.id,
            period="annual",
            period_date=date(2023, 9, 30),
            pe_ratio=Decimal("28.50"),
            pb_ratio=Decimal("45.12"),
            market_cap=Decimal("2800000000000"),
            roe=Decimal("1.48"),
        ),
        MarketMetric(
            company_id=company2.id,
            period="TTM",
            period_date=date(2024, 1, 26),
            pe_ratio=Decimal("35.67"),
            market_cap=Decimal("2750000000000"),
        ),
    ]
    session.add_all(metrics)
    await session.commit()
    return company, company2


class TestMetricsAPI:
    async def test_list_metrics(self, client, seeded_metrics):
        resp = await client.get("/api/v1/companies/AAPL/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_period_filter(self, client, seeded_metrics):
        resp = await client.get("/api/v1/companies/AAPL/metrics", params={"period": "TTM"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["period"] == "TTM"

    async def test_latest_metrics(self, client, seeded_metrics):
        resp = await client.get("/api/v1/companies/AAPL/metrics/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "TTM"
        assert data["pe_ratio"] is not None

    async def test_latest_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/metrics/latest")
        assert resp.status_code == 404

    async def test_compare_metrics(self, client, seeded_metrics):
        resp = await client.get(
            "/api/v1/metrics/compare",
            params={"metric": "pe_ratio", "tickers": ["AAPL", "MSFT"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tickers = {d["ticker"] for d in data}
        assert tickers == {"AAPL", "MSFT"}

    async def test_compare_invalid_metric(self, client, seeded_metrics):
        resp = await client.get(
            "/api/v1/metrics/compare",
            params={"metric": "invalid_field", "tickers": ["AAPL"]},
        )
        assert resp.status_code == 400

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/metrics")
        assert resp.status_code == 404
