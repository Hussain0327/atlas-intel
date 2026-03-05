"""Integration tests for institutional holdings sync — real DB + mocked FMP API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.institutional_sync import sync_institutional_holdings
from atlas_intel.models.company import Company
from atlas_intel.models.institutional_holding import InstitutionalHolding


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_alt_data_api")
class TestInstitutionalSync:
    async def test_sync_creates_holdings(self, session, company):
        async with FMPClient() as client:
            count = await sync_institutional_holdings(session, client, company, force=True)

        assert count == 3

        total = (
            await session.execute(
                select(func.count(InstitutionalHolding.id)).where(
                    InstitutionalHolding.company_id == company.id
                )
            )
        ).scalar()
        assert total == 3

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_institutional_holdings(session, client, company, force=True)
            await session.refresh(company)
            count2 = await sync_institutional_holdings(session, client, company, force=False)

        assert count2 == 0

    async def test_dedup_on_conflict(self, session, company):
        async with FMPClient() as client:
            await sync_institutional_holdings(session, client, company, force=True)
            count2 = await sync_institutional_holdings(session, client, company, force=True)

        assert count2 == 0

        total = (
            await session.execute(
                select(func.count(InstitutionalHolding.id)).where(
                    InstitutionalHolding.company_id == company.id
                )
            )
        ).scalar()
        assert total == 3

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_institutional_holdings(session, client, company, force=True)

        await session.refresh(company)
        assert company.institutional_holdings_synced_at is not None
