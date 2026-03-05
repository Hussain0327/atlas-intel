"""API tests for institutional holdings endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.institutional_holding import InstitutionalHolding


@pytest.fixture
async def seeded_holdings(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    holdings = [
        InstitutionalHolding(
            company_id=company.id,
            holder="Vanguard Group Inc",
            shares=1300000000,
            date_reported=date(2024, 1, 15),
            market_value=Decimal("253500000000"),
        ),
        InstitutionalHolding(
            company_id=company.id,
            holder="Blackrock Inc",
            shares=1050000000,
            date_reported=date(2024, 1, 15),
            market_value=Decimal("204750000000"),
        ),
        InstitutionalHolding(
            company_id=company.id,
            holder="Berkshire Hathaway Inc",
            shares=905000000,
            date_reported=date(2024, 1, 15),
            market_value=Decimal("176475000000"),
        ),
    ]
    session.add_all(holdings)
    await session.commit()
    return company


class TestInstitutionalAPI:
    async def test_list_holdings(self, client, seeded_holdings):
        resp = await client.get("/api/v1/companies/AAPL/institutional-holdings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_holdings_pagination(self, client, seeded_holdings):
        resp = await client.get(
            "/api/v1/companies/AAPL/institutional-holdings", params={"limit": 2}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    async def test_top_holders(self, client, seeded_holdings):
        resp = await client.get("/api/v1/companies/AAPL/institutional-holdings/top")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be ordered by shares desc
        assert data[0]["holder"] == "Vanguard Group Inc"

    async def test_top_holders_limit(self, client, seeded_holdings):
        resp = await client.get(
            "/api/v1/companies/AAPL/institutional-holdings/top", params={"limit": 1}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/institutional-holdings")
        assert resp.status_code == 404
