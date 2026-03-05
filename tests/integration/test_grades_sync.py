"""Integration tests for analyst grades and price targets sync."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.grades_sync import sync_analyst_grades, sync_price_targets
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.company import Company
from atlas_intel.models.price_target import PriceTarget


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_alt_data_api")
class TestGradesSync:
    async def test_sync_creates_grades(self, session, company):
        async with FMPClient() as client:
            count = await sync_analyst_grades(session, client, company, force=True)

        assert count == 3

        total = (
            await session.execute(
                select(func.count(AnalystGrade.id)).where(AnalystGrade.company_id == company.id)
            )
        ).scalar()
        assert total == 3

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_analyst_grades(session, client, company, force=True)
            await session.refresh(company)
            count2 = await sync_analyst_grades(session, client, company, force=False)

        assert count2 == 0

    async def test_dedup_on_conflict(self, session, company):
        async with FMPClient() as client:
            await sync_analyst_grades(session, client, company, force=True)
            count2 = await sync_analyst_grades(session, client, company, force=True)

        assert count2 == 0

        total = (
            await session.execute(
                select(func.count(AnalystGrade.id)).where(AnalystGrade.company_id == company.id)
            )
        ).scalar()
        assert total == 3

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_analyst_grades(session, client, company, force=True)

        await session.refresh(company)
        assert company.analyst_grades_synced_at is not None


@pytest.mark.usefixtures("mock_fmp_alt_data_api")
class TestPriceTargetsSync:
    async def test_sync_creates_target(self, session, company):
        async with FMPClient() as client:
            updated = await sync_price_targets(session, client, company, force=True)

        assert updated is True

        target = (
            await session.execute(select(PriceTarget).where(PriceTarget.company_id == company.id))
        ).scalar_one()
        assert target.target_consensus is not None

    async def test_upsert_updates(self, session, company):
        async with FMPClient() as client:
            await sync_price_targets(session, client, company, force=True)
            updated2 = await sync_price_targets(session, client, company, force=True)

        assert updated2 is True

        total = (
            await session.execute(
                select(func.count(PriceTarget.id)).where(PriceTarget.company_id == company.id)
            )
        ).scalar()
        assert total == 1

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_price_targets(session, client, company, force=True)
            await session.refresh(company)
            updated2 = await sync_price_targets(session, client, company, force=False)

        assert updated2 is False

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_price_targets(session, client, company, force=True)

        await session.refresh(company)
        assert company.price_targets_synced_at is not None
