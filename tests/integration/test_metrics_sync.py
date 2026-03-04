"""Integration tests for metrics sync — real DB + mocked FMP API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.metrics_sync import sync_metrics
from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_market_api")
class TestMetricsSync:
    async def test_sync_creates_metrics(self, session, company):
        async with FMPClient() as client:
            count = await sync_metrics(session, client, company, force=True)

        assert count > 0

        total = (
            await session.execute(
                select(func.count(MarketMetric.id)).where(MarketMetric.company_id == company.id)
            )
        ).scalar()
        assert total is not None and total > 0

    async def test_ttm_and_annual_periods(self, session, company):
        async with FMPClient() as client:
            await sync_metrics(session, client, company, force=True)

        result = await session.execute(
            select(MarketMetric.period).where(MarketMetric.company_id == company.id).distinct()
        )
        periods = {r[0] for r in result.all()}
        assert "TTM" in periods
        assert "annual" in periods

    async def test_sync_is_idempotent(self, session, company):
        async with FMPClient() as client:
            count1 = await sync_metrics(session, client, company, force=True)
            count2 = await sync_metrics(session, client, company, force=True)

        # Second sync should upsert same rows
        assert count2 == count1

        total = (
            await session.execute(
                select(func.count(MarketMetric.id)).where(MarketMetric.company_id == company.id)
            )
        ).scalar()
        # Should not double the records
        assert total == count1

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_metrics(session, client, company, force=True)
            await session.refresh(company)
            count2 = await sync_metrics(session, client, company, force=False)

        assert count2 == 0

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_metrics(session, client, company, force=True)

        await session.refresh(company)
        assert company.metrics_synced_at is not None
