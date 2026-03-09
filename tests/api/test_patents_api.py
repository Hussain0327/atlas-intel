"""API tests for patent endpoints."""

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.patent import Patent


@pytest.fixture
async def company_with_patents(session):
    from datetime import date

    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.flush()

    patents = [
        Patent(
            company_id=c.id,
            patent_number="US-12345678-B2",
            title="ML Inference System",
            grant_date=date(2025, 6, 15),
            patent_type="utility",
            cpc_class="G06N3/08",
            citation_count=42,
        ),
        Patent(
            company_id=c.id,
            patent_number="US-D999888-S1",
            title="Electronic Device",
            grant_date=date(2025, 4, 10),
            patent_type="design",
        ),
    ]
    session.add_all(patents)
    await session.commit()
    return c


class TestPatentsAPI:
    async def test_list_patents(self, client, session, company_with_patents):
        response = await client.get("/api/v1/companies/AAPL/patents")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    async def test_filter_by_type(self, client, session, company_with_patents):
        response = await client.get("/api/v1/companies/AAPL/patents?patent_type=utility")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    async def test_innovation_summary(self, client, session, company_with_patents):
        response = await client.get("/api/v1/companies/AAPL/patents/innovation")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["total_patents"] == 2
