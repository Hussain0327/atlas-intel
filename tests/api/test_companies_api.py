"""API tests for company endpoints."""

import pytest

from atlas_intel.models.company import Company


@pytest.fixture
async def seeded_company(session):
    company = Company(
        cik=320193,
        ticker="AAPL",
        name="Apple Inc.",
        exchange="Nasdaq",
        sic_code="3571",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


class TestCompaniesAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/v1/companies/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_with_data(self, client, seeded_company):
        resp = await client.get("/api/v1/companies/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(c["ticker"] == "AAPL" for c in data["items"])

    async def test_get_by_ticker(self, client, seeded_company):
        resp = await client.get("/api/v1/companies/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["cik"] == 320193
        assert data["name"] == "Apple Inc."

    async def test_get_by_cik(self, client, seeded_company):
        resp = await client.get("/api/v1/companies/320193")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    async def test_get_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ")
        assert resp.status_code == 404

    async def test_search_by_query(self, client, seeded_company):
        resp = await client.get("/api/v1/companies/", params={"q": "Apple"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_ranked_search_handles_typos(self, client, session):
        apple = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        applied = Company(cik=6951, ticker="AMAT", name="Applied Materials, Inc.")
        session.add_all([apple, applied])
        await session.commit()

        resp = await client.get("/api/v1/companies/", params={"q": "Aple"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["ticker"] == "AAPL"

    async def test_search_by_exchange(self, client, seeded_company):
        resp = await client.get("/api/v1/companies/", params={"exchange": "Nasdaq"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_pagination(self, client, seeded_company):
        resp = await client.get("/api/v1/companies/", params={"limit": 1, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1
        assert data["offset"] == 0
