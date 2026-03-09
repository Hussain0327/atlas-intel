"""Integration tests for 8-K event sync — real DB + mocked SEC API."""

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.event_sync import sync_material_events
from atlas_intel.models.company import Company

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
async def company(session):
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    return c


@pytest.fixture
def sec_8k_filings():
    return json.loads((FIXTURES_DIR / "sec_8k_filings.json").read_text())


@pytest.fixture
def mock_sec_submissions_api(sec_8k_filings):
    """Mock the submissions endpoint to return 8-K filings."""
    # Wrap filings in the submissions response format
    forms = [f["form"] for f in sec_8k_filings]
    dates = [f["filingDate"] for f in sec_8k_filings]
    accessions = [f["accessionNumber"] for f in sec_8k_filings]
    items = [f.get("items", "") for f in sec_8k_filings]
    descs = [f.get("description", "") for f in sec_8k_filings]

    submissions_response = {
        "cik": "320193",
        "name": "Apple Inc.",
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": dates,
                "accessionNumber": accessions,
                "items": items,
                "primaryDocDescription": descs,
                "primaryDocument": [""] * len(forms),
            },
            "files": [],
        },
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://data.sec.gov/submissions/").mock(
            return_value=Response(200, json=submissions_response)
        )
        yield mock


@pytest.mark.usefixtures("mock_sec_submissions_api")
class TestEventSync:
    async def test_sync_creates_events(self, session, company):
        async with SECClient() as client:
            count = await sync_material_events(session, client, company, force=True)

        # 3 filings, first has 2 items (5.02 + 8.01), so 4 events total
        assert count == 4
        await session.refresh(company)
        assert company.material_events_synced_at is not None

    async def test_freshness_skip(self, session, company):
        async with SECClient() as client:
            await sync_material_events(session, client, company, force=True)
            await session.refresh(company)
            count = await sync_material_events(session, client, company, force=False)

        assert count == 0

    async def test_idempotent(self, session, company):
        async with SECClient() as client:
            await sync_material_events(session, client, company, force=True)
            count = await sync_material_events(session, client, company, force=True)

        # ON CONFLICT DO NOTHING — second sync inserts 0
        assert count == 0


class TestEventSyncEmpty:
    async def test_empty_response(self, session):
        c = Company(cik=999999, ticker="ZZZZ", name="Empty Co")
        session.add(c)
        await session.commit()

        empty_submissions = {
            "cik": "999999",
            "name": "Empty Co",
            "filings": {
                "recent": {
                    "form": [],
                    "filingDate": [],
                    "accessionNumber": [],
                    "items": [],
                    "primaryDocDescription": [],
                    "primaryDocument": [],
                },
                "files": [],
            },
        }

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://data.sec.gov/submissions/").mock(
                return_value=Response(200, json=empty_submissions)
            )

            async with SECClient() as client:
                count = await sync_material_events(session, client, c, force=True)

        assert count == 0
        await session.refresh(c)
        assert c.material_events_synced_at is not None
