"""Integration tests for congress trading sync — real DB + mocked FMP API."""

import pytest
import respx
from httpx import Response

from atlas_intel.ingestion.congress_client import CongressClient
from atlas_intel.ingestion.congress_sync import sync_congress_trades
from atlas_intel.models.company import Company


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.fixture
def mock_congress_api():
    senate_data = [
        {
            "firstName": "John",
            "lastName": "Doe",
            "party": "D",
            "transactionDate": "2025-09-15",
            "disclosureDate": "2025-10-20",
            "type": "Purchase",
            "amount": "$1,001 - $15,000",
            "assetDescription": "Apple Inc. Common Stock",
        },
    ]
    house_data = [
        {
            "representative": "Bob Johnson",
            "party": "R",
            "transactDate": "2025-07-22",
            "transactionType": "purchase",
            "amount": "$1,001 - $15,000",
        },
    ]

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://financialmodelingprep.com/stable/senate-trading").mock(
            return_value=Response(200, json=senate_data)
        )
        mock.get(url__startswith="https://financialmodelingprep.com/stable/house-disclosure").mock(
            return_value=Response(200, json=house_data)
        )
        yield mock


@pytest.mark.usefixtures("mock_congress_api")
class TestCongressSync:
    async def test_sync_creates_trades(self, session, company):
        async with CongressClient() as client:
            count = await sync_congress_trades(session, client, company, force=True)

        assert count == 2
        await session.refresh(company)
        assert company.congress_trades_synced_at is not None

    async def test_freshness_skip(self, session, company):
        async with CongressClient() as client:
            await sync_congress_trades(session, client, company, force=True)
            await session.refresh(company)
            count = await sync_congress_trades(session, client, company, force=False)

        assert count == 0

    async def test_idempotent(self, session, company):
        async with CongressClient() as client:
            await sync_congress_trades(session, client, company, force=True)
            count = await sync_congress_trades(session, client, company, force=True)

        assert count == 0  # ON CONFLICT DO NOTHING


class TestCongressSyncEmpty:
    async def test_empty_response(self, session):
        c = Company(cik=999999, ticker="ZZZZ", name="Empty Co")
        session.add(c)
        await session.commit()

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/senate-trading"
            ).mock(return_value=Response(200, json=[]))
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/house-disclosure"
            ).mock(return_value=Response(200, json=[]))

            async with CongressClient() as client:
                count = await sync_congress_trades(session, client, c, force=True)

        assert count == 0
        await session.refresh(c)
        assert c.congress_trades_synced_at is not None
