"""Integration tests for submission sync — real DB + mocked SEC API."""

import pytest
from sqlalchemy import select

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.submission_sync import sync_submissions
from atlas_intel.ingestion.ticker_sync import sync_tickers
from atlas_intel.models.company import Company
from atlas_intel.models.filing import Filing


@pytest.mark.usefixtures("mock_sec_api")
class TestSubmissionSync:
    async def test_sync_creates_filings(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)

            result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
            company = result.scalar_one()

            count = await sync_submissions(session, client, company, force=True)

        assert count == 5

        result = await session.execute(select(Filing).where(Filing.company_id == company.id))
        filings = result.scalars().all()
        assert len(filings) == 5

        ten_k = [f for f in filings if f.form_type == "10-K"]
        assert len(ten_k) == 2

    async def test_updates_company_metadata(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)

            result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
            company = result.scalar_one()
            await sync_submissions(session, client, company, force=True)

        # Refresh company after sync
        await session.refresh(company)
        assert company.sic_code == "3571"
        assert company.exchange == "Nasdaq"
        assert company.fiscal_year_end == "0930"
        assert company.submissions_synced_at is not None

    async def test_sync_is_idempotent(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)

            result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
            company = result.scalar_one()

            await sync_submissions(session, client, company, force=True)
            await sync_submissions(session, client, company, force=True)

        result = await session.execute(select(Filing).where(Filing.company_id == company.id))
        filings = result.scalars().all()
        assert len(filings) == 5  # No duplicates
