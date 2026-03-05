"""Integration tests for analyst estimates sync — real DB + mocked FMP API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.estimates_sync import sync_analyst_estimates
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.models.analyst_estimate import AnalystEstimate
from atlas_intel.models.company import Company


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_alt_data_api")
class TestEstimatesSync:
    async def test_sync_creates_estimates(self, session, company):
        async with FMPClient() as client:
            count = await sync_analyst_estimates(session, client, company, force=True)

        # 2 annual + 2 quarterly from fixture
        assert count == 4

        total = (
            await session.execute(
                select(func.count(AnalystEstimate.id)).where(
                    AnalystEstimate.company_id == company.id
                )
            )
        ).scalar()
        assert total == 4

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_analyst_estimates(session, client, company, force=True)
            await session.refresh(company)
            count2 = await sync_analyst_estimates(session, client, company, force=False)

        assert count2 == 0

    async def test_upsert_updates(self, session, company):
        async with FMPClient() as client:
            await sync_analyst_estimates(session, client, company, force=True)
            count2 = await sync_analyst_estimates(session, client, company, force=True)

        # ON CONFLICT DO UPDATE → rows updated
        assert count2 == 4

        total = (
            await session.execute(
                select(func.count(AnalystEstimate.id)).where(
                    AnalystEstimate.company_id == company.id
                )
            )
        ).scalar()
        assert total == 4  # Still 4, not 8

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_analyst_estimates(session, client, company, force=True)

        await session.refresh(company)
        assert company.analyst_estimates_synced_at is not None
