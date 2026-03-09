"""API tests for fusion signal endpoints."""

import pytest

from atlas_intel.models.company import Company


@pytest.fixture
async def signal_company(session):
    c = Company(cik=111111, ticker="TSLA", name="Tesla Inc.")
    session.add(c)
    await session.commit()
    return c


class TestSignalsAPI:
    async def test_all_signals(self, client, session, signal_company):
        response = await client.get("/api/v1/companies/TSLA/signals")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TSLA"
        assert "sentiment" in data
        assert "growth" in data
        assert "risk" in data
        assert "smart_money" in data
        # All signals should have confidence 0 since there's no data
        for signal_key in ["sentiment", "growth", "risk", "smart_money"]:
            signal = data[signal_key]
            assert signal["confidence"] == 0.0
            assert signal["label"] is not None

    async def test_sentiment_signal(self, client, session, signal_company):
        response = await client.get("/api/v1/companies/TSLA/signals/sentiment")
        assert response.status_code == 200
        data = response.json()
        assert data["signal_type"] == "sentiment"
        assert "components" in data

    async def test_growth_signal(self, client, session, signal_company):
        response = await client.get("/api/v1/companies/TSLA/signals/growth")
        assert response.status_code == 200
        data = response.json()
        assert data["signal_type"] == "growth"

    async def test_risk_signal(self, client, session, signal_company):
        response = await client.get("/api/v1/companies/TSLA/signals/risk")
        assert response.status_code == 200
        data = response.json()
        assert data["signal_type"] == "risk"

    async def test_smart_money_signal(self, client, session, signal_company):
        response = await client.get("/api/v1/companies/TSLA/signals/smart-money")
        assert response.status_code == 200
        data = response.json()
        assert data["signal_type"] == "smart_money"

    async def test_company_not_found(self, client, session):
        response = await client.get("/api/v1/companies/ZZZZ/signals")
        assert response.status_code == 404
