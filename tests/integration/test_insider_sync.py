"""Integration tests for insider trading sync — real DB + mocked FMP API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.insider_sync import sync_insider_trades
from atlas_intel.models.company import Company
from atlas_intel.models.insider_trade import InsiderTrade


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_alt_data_api")
class TestInsiderSync:
    async def test_sync_creates_trades(self, session, company):
        async with FMPClient() as client:
            count = await sync_insider_trades(session, client, company, force=True)

        assert count == 3

        total = (
            await session.execute(
                select(func.count(InsiderTrade.id)).where(InsiderTrade.company_id == company.id)
            )
        ).scalar()
        assert total == 3

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_insider_trades(session, client, company, force=True)
            await session.refresh(company)
            count2 = await sync_insider_trades(session, client, company, force=False)

        assert count2 == 0

    async def test_dedup_on_conflict(self, session, company):
        async with FMPClient() as client:
            await sync_insider_trades(session, client, company, force=True)
            count2 = await sync_insider_trades(session, client, company, force=True)

        # DO NOTHING on conflict → 0 new inserts
        assert count2 == 0

        total = (
            await session.execute(
                select(func.count(InsiderTrade.id)).where(InsiderTrade.company_id == company.id)
            )
        ).scalar()
        assert total == 3

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_insider_trades(session, client, company, force=True)

        await session.refresh(company)
        assert company.insider_trades_synced_at is not None
