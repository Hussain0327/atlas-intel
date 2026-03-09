"""API tests for congress trading endpoints."""

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.congress_trade import CongressTrade


@pytest.fixture
async def company_with_congress(session):
    from datetime import date

    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.flush()

    trades = [
        CongressTrade(
            company_id=c.id,
            representative="John Doe",
            party="D",
            chamber="Senate",
            transaction_date=date(2025, 9, 15),
            transaction_type="purchase",
            amount_range="$1,001 - $15,000",
        ),
        CongressTrade(
            company_id=c.id,
            representative="Jane Smith",
            party="R",
            chamber="House",
            transaction_date=date(2025, 8, 10),
            transaction_type="sale",
            amount_range="$15,001 - $50,000",
        ),
    ]
    session.add_all(trades)
    await session.commit()
    return c


class TestCongressAPI:
    async def test_list_trades(self, client, session, company_with_congress):
        response = await client.get("/api/v1/companies/AAPL/congress")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    async def test_filter_by_party(self, client, session, company_with_congress):
        response = await client.get("/api/v1/companies/AAPL/congress?party=D")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["party"] == "D"

    async def test_congress_summary(self, client, session, company_with_congress):
        response = await client.get("/api/v1/companies/AAPL/congress/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["total_trades"] == 2
        assert data["purchases"] == 1
        assert data["sales"] == 1
        assert data["democrat_trades"] == 1
        assert data["republican_trades"] == 1
