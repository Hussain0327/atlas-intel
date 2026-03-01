"""API tests for filing endpoints."""

from datetime import date

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.filing import Filing


@pytest.fixture
async def seeded_filings(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    filings = [
        Filing(
            company_id=company.id,
            accession_number="000032019324000123",
            form_type="10-K",
            filing_date=date(2024, 11, 1),
            period_of_report=date(2024, 9, 28),
            is_xbrl=True,
        ),
        Filing(
            company_id=company.id,
            accession_number="000032019324000081",
            form_type="10-Q",
            filing_date=date(2024, 8, 2),
            period_of_report=date(2024, 6, 29),
            is_xbrl=True,
        ),
    ]
    session.add_all(filings)
    await session.commit()
    return company, filings


class TestFilingsAPI:
    async def test_list_filings(self, client, seeded_filings):
        resp = await client.get("/api/v1/companies/AAPL/filings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_filter_by_form_type(self, client, seeded_filings):
        resp = await client.get("/api/v1/companies/AAPL/filings/", params={"form_type": "10-K"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["form_type"] == "10-K"

    async def test_get_filing_by_accession(self, client, seeded_filings):
        resp = await client.get("/api/v1/companies/AAPL/filings/000032019324000123")
        assert resp.status_code == 200
        assert resp.json()["form_type"] == "10-K"

    async def test_filing_not_found(self, client, seeded_filings):
        resp = await client.get("/api/v1/companies/AAPL/filings/000000000000000000")
        assert resp.status_code == 404

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/filings/")
        assert resp.status_code == 404
