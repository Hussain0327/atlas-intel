"""Integration tests for ticker sync — real DB + mocked SEC API."""

import pytest
from sqlalchemy import select

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.ticker_sync import sync_tickers
from atlas_intel.models.company import Company


@pytest.mark.usefixtures("mock_sec_api")
class TestTickerSync:
    async def test_sync_creates_companies(self, session):
        async with SECClient() as client:
            count = await sync_tickers(session, client)

        assert count == 7

        result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
        aapl = result.scalar_one()
        assert aapl.cik == 320193
        assert aapl.name == "Apple Inc."

    async def test_sync_is_idempotent(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)
            count2 = await sync_tickers(session, client)

        assert count2 == 7  # Upserts, not duplicates

        result = await session.execute(select(Company))
        companies = result.scalars().all()
        assert len(companies) == 7
