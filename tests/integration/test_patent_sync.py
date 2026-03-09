"""Integration tests for patent sync — real DB + mocked USPTO API."""

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from atlas_intel.ingestion.patent_client import PatentClient
from atlas_intel.ingestion.patent_sync import sync_patents
from atlas_intel.models.company import Company

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.", sector="Technology")
    session.add(c)
    await session.commit()
    return c


@pytest.fixture
def uspto_json():
    return json.loads((FIXTURES_DIR / "uspto_patents.json").read_text())


@pytest.fixture
def mock_uspto_api(uspto_json):
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://search.patentsview.org/api/v1/patent/").mock(
            return_value=Response(200, json=uspto_json)
        )
        yield mock


@pytest.mark.usefixtures("mock_uspto_api")
class TestPatentSync:
    async def test_sync_creates_patents(self, session, company):
        async with PatentClient(api_key="test_key") as client:
            count = await sync_patents(session, client, company, force=True)

        assert count == 3
        await session.refresh(company)
        assert company.patents_synced_at is not None

    async def test_freshness_skip(self, session, company):
        async with PatentClient(api_key="test_key") as client:
            await sync_patents(session, client, company, force=True)
            await session.refresh(company)
            count = await sync_patents(session, client, company, force=False)

        assert count == 0

    async def test_idempotent(self, session, company):
        async with PatentClient(api_key="test_key") as client:
            await sync_patents(session, client, company, force=True)
            count = await sync_patents(session, client, company, force=True)

        assert count == 0  # ON CONFLICT DO NOTHING


class TestPatentSyncSkipFinancial:
    async def test_skips_financial_sector(self, session):
        c = Company(cik=19617, ticker="JPM", name="JPMorgan", sector="Financial Services")
        session.add(c)
        await session.commit()

        async with PatentClient(api_key="test_key") as client:
            count = await sync_patents(session, client, c, force=True)

        assert count == 0
        await session.refresh(c)
        assert c.patents_synced_at is not None


class TestPatentSyncEmpty:
    async def test_empty_response(self, session):
        c = Company(cik=999999, ticker="ZZZZ", name="Empty Co")
        session.add(c)
        await session.commit()

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://search.patentsview.org/api/v1/patent/").mock(
                return_value=Response(200, json={"patents": []})
            )

            async with PatentClient(api_key="test_key") as client:
                count = await sync_patents(session, client, c, force=True)

        assert count == 0
        await session.refresh(c)
        assert c.patents_synced_at is not None
