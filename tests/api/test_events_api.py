"""API tests for material event endpoints."""

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.material_event import MaterialEvent


@pytest.fixture
async def company_with_events(session):
    from datetime import date

    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.flush()

    events = [
        MaterialEvent(
            company_id=c.id,
            event_date=date(2025, 11, 15),
            event_type="officer_change",
            item_number="5.02",
            accession_number="0000320193-25-000099",
            source="sec_8k",
        ),
        MaterialEvent(
            company_id=c.id,
            event_date=date(2025, 10, 1),
            event_type="operating_results",
            item_number="2.02",
            accession_number="0000320193-25-000088",
            source="sec_8k",
        ),
    ]
    session.add_all(events)
    await session.commit()
    return c


class TestEventsAPI:
    async def test_list_events(self, client, session, company_with_events):
        response = await client.get("/api/v1/companies/AAPL/events")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    async def test_filter_by_type(self, client, session, company_with_events):
        response = await client.get("/api/v1/companies/AAPL/events?event_type=officer_change")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["event_type"] == "officer_change"

    async def test_event_summary(self, client, session, company_with_events):
        response = await client.get("/api/v1/companies/AAPL/events/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["total_events"] == 2

    async def test_company_not_found(self, client, session):
        response = await client.get("/api/v1/companies/ZZZZ/events")
        assert response.status_code == 404
