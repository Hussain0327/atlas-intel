"""API tests for news endpoints."""

from datetime import datetime

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.news_article import NewsArticle


@pytest.fixture
async def seeded_news(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    articles = [
        NewsArticle(
            company_id=company.id,
            title="Article 1",
            url="https://example.com/1",
            source_name="Bloomberg",
            published_at=datetime(2024, 1, 26, 14, 0),
        ),
        NewsArticle(
            company_id=company.id,
            title="Article 2",
            url="https://example.com/2",
            source_name="Reuters",
            published_at=datetime(2024, 1, 25, 10, 0),
        ),
        NewsArticle(
            company_id=company.id,
            title="Article 3",
            url="https://example.com/3",
            source_name="Bloomberg",
            published_at=datetime(2024, 1, 24, 8, 0),
        ),
    ]
    session.add_all(articles)
    await session.commit()
    return company


class TestNewsAPI:
    async def test_list_news(self, client, seeded_news):
        resp = await client.get("/api/v1/companies/AAPL/news")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_news_pagination(self, client, seeded_news):
        resp = await client.get("/api/v1/companies/AAPL/news", params={"limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    async def test_news_activity(self, client, seeded_news):
        resp = await client.get("/api/v1/companies/AAPL/news/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "unique_sources" in data

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/news")
        assert resp.status_code == 404
