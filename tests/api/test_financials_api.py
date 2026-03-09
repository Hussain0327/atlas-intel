"""API tests for financial endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.financial_fact import FinancialFact


@pytest.fixture
async def seeded_financials(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    company2 = Company(cik=789019, ticker="MSFT", name="Microsoft Corp")
    session.add(company2)
    await session.flush()

    facts = [
        FinancialFact(
            company_id=company.id,
            taxonomy="us-gaap",
            concept="Revenues",
            value=Decimal("383285000000"),
            unit="USD",
            period_start=date(2022, 10, 1),
            period_end=date(2023, 9, 30),
            is_instant=False,
            fiscal_year=2023,
            fiscal_period="FY",
            form_type="10-K",
            accession_number="000032019323000106",
            filed_date=date(2023, 11, 3),
        ),
        FinancialFact(
            company_id=company.id,
            taxonomy="us-gaap",
            concept="Revenues",
            value=Decimal("394328000000"),
            unit="USD",
            period_start=date(2021, 9, 26),
            period_end=date(2022, 9, 24),
            is_instant=False,
            fiscal_year=2022,
            fiscal_period="FY",
            form_type="10-K",
            accession_number="000032019322000108",
            filed_date=date(2022, 10, 28),
        ),
        FinancialFact(
            company_id=company2.id,
            taxonomy="us-gaap",
            concept="Revenues",
            value=Decimal("211915000000"),
            unit="USD",
            period_start=date(2022, 7, 1),
            period_end=date(2023, 6, 30),
            is_instant=False,
            fiscal_year=2023,
            fiscal_period="FY",
            form_type="10-K",
            accession_number="000078901923000100",
            filed_date=date(2023, 7, 25),
        ),
    ]
    session.add_all(facts)
    await session.commit()
    return company, company2


class TestFinancialsAPI:
    async def test_query_all_facts(self, client, seeded_financials):
        resp = await client.get("/api/v1/companies/AAPL/financials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_filter_by_concept(self, client, seeded_financials):
        resp = await client.get("/api/v1/companies/AAPL/financials", params={"concept": "Revenues"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_filter_by_fiscal_year(self, client, seeded_financials):
        resp = await client.get(
            "/api/v1/companies/AAPL/financials",
            params={"concept": "Revenues", "fiscal_year": 2023},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["fiscal_year"] == 2023

    async def test_summary(self, client, seeded_financials):
        resp = await client.get("/api/v1/companies/AAPL/financials/summary")
        assert resp.status_code == 200
        data = resp.json()
        revenue_entry = next((d for d in data if d["concept"] == "Revenues"), None)
        assert revenue_entry is not None
        assert len(revenue_entry["values"]) == 2

    async def test_compare(self, client, seeded_financials):
        resp = await client.get(
            "/api/v1/financials/compare",
            params={"concept": "Revenues", "tickers": ["AAPL", "MSFT"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tickers = {d["ticker"] for d in data}
        assert tickers == {"AAPL", "MSFT"}

    async def test_compare_sets_unresolved_header(self, client, seeded_financials):
        resp = await client.get(
            "/api/v1/financials/compare",
            params={"concept": "Revenues", "tickers": ["AAPL", "MISSING"]},
        )

        assert resp.status_code == 200
        assert resp.headers["X-Unresolved-Tickers"] == "MISSING"
        assert len(resp.json()) == 1

    async def test_compare_report(self, client, seeded_financials):
        resp = await client.get(
            "/api/v1/financials/compare/report",
            params={"concept": "Revenues", "tickers": ["AAPL", "MISSING"]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["requested_tickers"] == ["AAPL", "MISSING"]
        assert data["unresolved_tickers"] == ["MISSING"]
        assert len(data["items"]) == 1

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/financials")
        assert resp.status_code == 404
