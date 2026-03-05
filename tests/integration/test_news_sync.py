"""Integration tests for news sync — real DB + mocked FMP API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.news_sync import sync_news
from atlas_intel.models.company import Company
from atlas_intel.models.news_article import NewsArticle


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_alt_data_api")
class TestNewsSync:
    async def test_sync_creates_articles(self, session, company):
        async with FMPClient() as client:
            count = await sync_news(session, client, company, force=True)

        assert count == 3

        total = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(NewsArticle.company_id == company.id)
            )
        ).scalar()
        assert total == 3

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_news(session, client, company, force=True)
            await session.refresh(company)
            count2 = await sync_news(session, client, company, force=False)

        assert count2 == 0

    async def test_idempotent_upsert(self, session, company):
        async with FMPClient() as client:
            await sync_news(session, client, company, force=True)
            count2 = await sync_news(session, client, company, force=True)

        assert count2 == 3  # Upsert updates existing

        total = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(NewsArticle.company_id == company.id)
            )
        ).scalar()
        assert total == 3

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_news(session, client, company, force=True)

        await session.refresh(company)
        assert company.news_synced_at is not None
