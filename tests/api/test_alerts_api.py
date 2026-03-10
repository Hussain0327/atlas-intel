"""API tests for alert management endpoints."""

import pytest

from atlas_intel.models.company import Company


class TestAlertRulesCRUD:
    async def test_create_rule(self, client, session):
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        resp = await client.post(
            "/api/v1/alerts/rules",
            json={
                "company_id": company.id,
                "name": "AAPL price drop",
                "rule_type": "price_threshold",
                "conditions": {"field": "close", "op": "lt", "value": 150.0},
                "cooldown_minutes": 120,
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "AAPL price drop"
        assert data["rule_type"] == "price_threshold"
        assert data["enabled"] is True
        assert data["cooldown_minutes"] == 120

    async def test_create_rule_invalid_type(self, client):
        resp = await client.post(
            "/api/v1/alerts/rules",
            json={
                "name": "bad rule",
                "rule_type": "invalid_type",
                "conditions": {},
            },
        )
        assert resp.status_code == 422

    async def test_list_rules(self, client, session):
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        await client.post(
            "/api/v1/alerts/rules",
            json={
                "company_id": company.id,
                "name": "Rule 1",
                "rule_type": "price_threshold",
                "conditions": {"field": "close", "op": "lt", "value": 100},
            },
        )
        await client.post(
            "/api/v1/alerts/rules",
            json={
                "name": "Rule 2",
                "rule_type": "volume_spike",
                "conditions": {"multiplier": 2.0},
            },
        )

        resp = await client.get("/api/v1/alerts/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_get_rule(self, client, session):
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        create_resp = await client.post(
            "/api/v1/alerts/rules",
            json={
                "company_id": company.id,
                "name": "Test Rule",
                "rule_type": "price_threshold",
                "conditions": {"field": "close", "op": "lt", "value": 100},
            },
        )
        rule_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/alerts/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Rule"

    async def test_get_rule_not_found(self, client):
        resp = await client.get("/api/v1/alerts/rules/999")
        assert resp.status_code == 404

    async def test_update_rule(self, client, session):
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        create_resp = await client.post(
            "/api/v1/alerts/rules",
            json={
                "company_id": company.id,
                "name": "Old Name",
                "rule_type": "price_threshold",
                "conditions": {"field": "close", "op": "lt", "value": 100},
            },
        )
        rule_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/alerts/rules/{rule_id}",
            json={"name": "New Name", "enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["enabled"] is False

    async def test_delete_rule(self, client, session):
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        create_resp = await client.post(
            "/api/v1/alerts/rules",
            json={
                "company_id": company.id,
                "name": "Deleteme",
                "rule_type": "price_threshold",
                "conditions": {},
            },
        )
        rule_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/alerts/rules/{rule_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/v1/alerts/rules/{rule_id}")
        assert resp.status_code == 404


class TestAlertEvents:
    async def test_list_events_empty(self, client):
        resp = await client.get("/api/v1/alerts/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["unacknowledged"] == 0

    async def test_ack_event_not_found(self, client):
        resp = await client.post("/api/v1/alerts/events/999/ack")
        assert resp.status_code == 404

    async def test_ack_all_empty(self, client):
        resp = await client.post("/api/v1/alerts/events/ack-all")
        assert resp.status_code == 200
        assert resp.json()["acknowledged"] == 0


class TestManualCheck:
    async def test_check_no_rules(self, client):
        resp = await client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        assert resp.json() == []
