"""Integration tests for facts sync — real DB + mocked SEC API."""

import pytest
from sqlalchemy import func, select

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.facts_sync import sync_facts
from atlas_intel.ingestion.ticker_sync import sync_tickers
from atlas_intel.models.company import Company
from atlas_intel.models.financial_fact import FinancialFact


@pytest.mark.usefixtures("mock_sec_api")
class TestFactsSync:
    async def test_sync_creates_facts(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)

            result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
            company = result.scalar_one()

            count = await sync_facts(session, client, company, force=True)

        assert count > 0

        total = (
            await session.execute(
                select(func.count(FinancialFact.id)).where(FinancialFact.company_id == company.id)
            )
        ).scalar()
        assert total is not None and total > 0

    async def test_revenue_facts_correct(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)

            result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
            company = result.scalar_one()

            await sync_facts(session, client, company, force=True)

        result = await session.execute(
            select(FinancialFact).where(
                FinancialFact.company_id == company.id,
                FinancialFact.concept == "Revenues",
                FinancialFact.fiscal_period == "FY",
            )
        )
        revenues = result.scalars().all()
        assert len(revenues) == 2  # FY2023 and FY2022

    async def test_sync_is_idempotent(self, session):
        async with SECClient() as client:
            await sync_tickers(session, client)

            result = await session.execute(select(Company).where(Company.ticker == "AAPL"))
            company = result.scalar_one()

            await sync_facts(session, client, company, force=True)
            count2 = await sync_facts(session, client, company, force=True)

        # Second sync should insert 0 new facts (ON CONFLICT DO NOTHING)
        assert count2 == 0
