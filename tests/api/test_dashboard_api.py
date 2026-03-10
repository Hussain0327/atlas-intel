"""API tests for dashboard endpoints."""

import pytest


class TestDashboard:
    async def test_full_dashboard(self, client):
        resp = await client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "market_overview" in data
        assert "top_movers" in data
        assert "alert_summary" in data

    async def test_market_overview(self, client):
        resp = await client.get("/api/v1/dashboard/market-overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_companies" in data
        assert "sectors" in data

    async def test_top_movers(self, client):
        resp = await client.get("/api/v1/dashboard/top-movers")
        assert resp.status_code == 200
        data = resp.json()
        assert "gainers" in data
        assert "losers" in data
        assert "volume_leaders" in data

    async def test_top_movers_with_params(self, client):
        resp = await client.get("/api/v1/dashboard/top-movers?lookback_days=7&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lookback_days"] == 7

    async def test_alert_summary(self, client):
        resp = await client.get("/api/v1/dashboard/alert-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_rules" in data
        assert "active_rules" in data
        assert "total_events_24h" in data

    async def test_dashboard_with_data(self, client, session):
        from atlas_intel.models.company import Company

        session.add(Company(cik=320193, ticker="AAPL", name="Apple Inc.", sector="Technology"))
        session.add(Company(cik=789019, ticker="MSFT", name="Microsoft Corp.", sector="Technology"))
        await session.commit()

        resp = await client.get("/api/v1/dashboard/market-overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_companies"] == 2
