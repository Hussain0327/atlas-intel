"""API tests for anomaly detection endpoints."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.stock_price import StockPrice


@pytest.fixture
async def anomaly_company(session):
    c = Company(
        cik=333333,
        ticker="GOOG",
        name="Alphabet Inc",
        sector="Technology",
    )
    session.add(c)
    await session.commit()
    return c


@pytest.fixture
async def price_data(session, anomaly_company):
    """Create 100 days of price data with a volume spike."""
    cid = anomaly_company.id
    base_date = date.today() - timedelta(days=100)

    for i in range(100):
        d = base_date + timedelta(days=i)
        volume = 1000000
        close = Decimal("150.00") + Decimal(str(i * 0.1))

        # Add a volume spike on day 80
        if i == 80:
            volume = 20000000  # 20x normal

        session.add(
            StockPrice(
                company_id=cid,
                price_date=d,
                open=close - Decimal("1"),
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                volume=volume,
            )
        )

    await session.commit()


class TestAnomalyAPI:
    async def test_all_anomalies(self, client, session, anomaly_company, price_data):
        response = await client.get("/api/v1/companies/GOOG/anomalies")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GOOG"
        assert "price" in data
        assert "fundamental" in data
        assert "activity" in data
        assert "sector" in data
        assert "total_anomalies" in data

    async def test_price_anomalies(self, client, session, anomaly_company, price_data):
        response = await client.get("/api/v1/companies/GOOG/anomalies/price")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GOOG"
        assert "volume_spikes" in data
        assert "return_spikes" in data
        assert "volatility_breakouts" in data

    async def test_fundamental_anomalies(self, client, session, anomaly_company):
        response = await client.get("/api/v1/companies/GOOG/anomalies/fundamental")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GOOG"
        assert data["total_anomalies"] == 0  # No metrics data

    async def test_activity_anomalies(self, client, session, anomaly_company):
        response = await client.get("/api/v1/companies/GOOG/anomalies/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GOOG"

    async def test_sector_anomalies(self, client, session, anomaly_company):
        response = await client.get("/api/v1/companies/GOOG/anomalies/sector")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GOOG"
        assert data["sector"] == "Technology"

    async def test_anomaly_company_not_found(self, client, session):
        response = await client.get("/api/v1/companies/ZZZZ/anomalies")
        assert response.status_code == 404

    async def test_custom_lookback(self, client, session, anomaly_company, price_data):
        response = await client.get("/api/v1/companies/GOOG/anomalies/price?lookback_days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["lookback_days"] == 30

    async def test_custom_threshold(self, client, session, anomaly_company, price_data):
        response = await client.get("/api/v1/companies/GOOG/anomalies/price?threshold=3.0")
        assert response.status_code == 200
        data = response.json()
        assert data["threshold"] == 3.0
