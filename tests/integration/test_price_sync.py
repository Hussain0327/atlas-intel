"""Integration tests for price sync — real DB + mocked FMP API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.price_sync import sync_prices
from atlas_intel.models.company import Company
from atlas_intel.models.stock_price import StockPrice


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_market_api")
class TestPriceSync:
    async def test_sync_creates_prices(self, session, company):
        async with FMPClient() as client:
            count = await sync_prices(session, client, company, force=True)

        assert count == 5  # 5 price entries in fixture

        total = (
            await session.execute(
                select(func.count(StockPrice.id)).where(StockPrice.company_id == company.id)
            )
        ).scalar()
        assert total == 5

    async def test_sync_is_idempotent(self, session, company):
        async with FMPClient() as client:
            await sync_prices(session, client, company, force=True)
            count2 = await sync_prices(session, client, company, force=True)

        # Second sync should upsert (update) the same rows
        assert count2 == 5

        total = (
            await session.execute(
                select(func.count(StockPrice.id)).where(StockPrice.company_id == company.id)
            )
        ).scalar()
        assert total == 5  # Still 5, not 10

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_prices(session, client, company, force=True)
            await session.refresh(company)
            # Second sync without force should skip (freshness check)
            count2 = await sync_prices(session, client, company, force=False)

        assert count2 == 0

    async def test_updates_sync_timestamp(self, session, company):
        async with FMPClient() as client:
            await sync_prices(session, client, company, force=True)

        await session.refresh(company)
        assert company.prices_synced_at is not None
