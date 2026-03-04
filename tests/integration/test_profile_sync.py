"""Integration tests for profile sync — real DB + mocked FMP API."""

import pytest
from httpx import Response

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.profile_sync import sync_profile
from atlas_intel.models.company import Company


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.mark.usefixtures("mock_fmp_market_api")
class TestProfileSync:
    async def test_sync_updates_profile(self, session, company):
        async with FMPClient() as client:
            updated = await sync_profile(session, client, company, force=True)

        assert updated is True
        await session.refresh(company)
        assert company.sector == "Technology"
        assert company.industry == "Consumer Electronics"
        assert company.ceo == "Mr. Timothy D. Cook"
        assert company.full_time_employees == 161000
        assert company.is_etf is False
        assert company.is_actively_trading is True
        assert company.profile_synced_at is not None

    async def test_freshness_skip(self, session, company):
        async with FMPClient() as client:
            await sync_profile(session, client, company, force=True)
            await session.refresh(company)
            updated = await sync_profile(session, client, company, force=False)

        assert updated is False


@pytest.fixture
async def company_for_empty_test(session):
    c = Company(cik=999999, ticker="ZZZZ", name="Empty Co")
    session.add(c)
    await session.commit()
    return c


class TestProfileSyncEmpty:
    async def test_empty_profile(self, session, company_for_empty_test):
        import respx

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://financialmodelingprep.com/stable/profile").mock(
                return_value=Response(200, json=[])
            )

            async with FMPClient() as client:
                updated = await sync_profile(session, client, company_for_empty_test, force=True)

        assert updated is False
