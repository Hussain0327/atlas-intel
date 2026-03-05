"""API tests for insider trading endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.insider_trade import InsiderTrade


@pytest.fixture
async def seeded_insider(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    trades = [
        InsiderTrade(
            company_id=company.id,
            filing_date=date(2024, 1, 20),
            transaction_date=date(2024, 1, 18),
            reporting_name="Tim Cook",
            reporting_cik="001",
            transaction_type="S",
            securities_transacted=Decimal("50000"),
            price=Decimal("195.50"),
            owner_type="officer",
        ),
        InsiderTrade(
            company_id=company.id,
            filing_date=date(2024, 1, 10),
            transaction_date=date(2024, 1, 8),
            reporting_name="Art Levinson",
            reporting_cik="002",
            transaction_type="P",
            securities_transacted=Decimal("10000"),
            price=Decimal("185.00"),
            owner_type="director",
        ),
    ]
    session.add_all(trades)
    await session.commit()
    return company


class TestInsiderAPI:
    async def test_list_insider_trades(self, client, seeded_insider):
        resp = await client.get("/api/v1/companies/AAPL/insider-trades")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_insider_sentiment(self, client, seeded_insider):
        resp = await client.get("/api/v1/companies/AAPL/insider-trades/sentiment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "sentiment" in data
        assert "buy_count" in data

    async def test_insider_sentiment_custom_days(self, client, seeded_insider):
        resp = await client.get(
            "/api/v1/companies/AAPL/insider-trades/sentiment", params={"days": 30}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 30

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/insider-trades")
        assert resp.status_code == 404
