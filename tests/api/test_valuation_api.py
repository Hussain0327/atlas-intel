"""API tests for valuation endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.company import Company
from atlas_intel.models.financial_fact import FinancialFact
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.models.price_target import PriceTarget
from atlas_intel.models.stock_price import StockPrice


@pytest.fixture
async def valuation_company(session):
    c = Company(
        cik=222222,
        ticker="MSFT",
        name="Microsoft Corp",
        sector="Technology",
        beta=Decimal("0.9"),
    )
    session.add(c)
    await session.commit()
    return c


@pytest.fixture
async def valuation_data(session, valuation_company):
    """Set up financial facts, prices, metrics, and price targets for valuation."""
    cid = valuation_company.id

    # OCF facts (annual)
    for year, val in [(2023, 80e9), (2022, 70e9), (2021, 60e9)]:
        session.add(
            FinancialFact(
                company_id=cid,
                taxonomy="us-gaap",
                concept="NetCashProvidedByUsedInOperatingActivities",
                value=Decimal(str(val)),
                unit="USD",
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                fiscal_year=year,
                fiscal_period="FY",
                form_type="10-K",
            )
        )

    # CapEx facts
    for year, val in [(2023, 20e9), (2022, 18e9), (2021, 15e9)]:
        session.add(
            FinancialFact(
                company_id=cid,
                taxonomy="us-gaap",
                concept="PaymentsToAcquirePropertyPlantAndEquipment",
                value=Decimal(str(val)),
                unit="USD",
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                fiscal_year=year,
                fiscal_period="FY",
                form_type="10-K",
            )
        )

    # Shares outstanding
    session.add(
        FinancialFact(
            company_id=cid,
            taxonomy="us-gaap",
            concept="CommonStockSharesOutstanding",
            value=Decimal("7500000000"),
            unit="shares",
            period_end=date(2023, 12, 31),
            is_instant=True,
            fiscal_year=2023,
            fiscal_period="FY",
            form_type="10-K",
        )
    )

    # Stock price
    session.add(
        StockPrice(
            company_id=cid,
            price_date=date(2024, 1, 15),
            close=Decimal("400.00"),
            volume=50000000,
        )
    )

    # Market metrics (TTM)
    session.add(
        MarketMetric(
            company_id=cid,
            period="TTM",
            period_date=date(2024, 1, 15),
            pe_ratio=Decimal("35.0"),
            pb_ratio=Decimal("12.0"),
            ev_to_ebitda=Decimal("25.0"),
            price_to_sales=Decimal("12.0"),
            ev_to_sales=Decimal("13.0"),
            market_cap=Decimal("3000000000000"),
            roe=Decimal("0.40"),
        )
    )

    # Price target
    session.add(
        PriceTarget(
            company_id=cid,
            target_consensus=Decimal("450.00"),
            target_high=Decimal("500.00"),
            target_low=Decimal("350.00"),
        )
    )

    await session.commit()


class TestValuationAPI:
    async def test_full_valuation(self, client, session, valuation_company, valuation_data):
        response = await client.get("/api/v1/companies/MSFT/valuation")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "MSFT"
        assert "dcf" in data
        assert "relative" in data
        assert "analyst" in data
        assert data["computed_at"] is not None

    async def test_dcf_valuation(self, client, session, valuation_company, valuation_data):
        response = await client.get("/api/v1/companies/MSFT/valuation/dcf")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "MSFT"
        assert data["data_quality"] in ("insufficient", "limited", "good")
        if data["scenarios"]:
            labels = [s["label"] for s in data["scenarios"]]
            assert "base" in labels

    async def test_relative_valuation(self, client, session, valuation_company, valuation_data):
        response = await client.get("/api/v1/companies/MSFT/valuation/relative")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "MSFT"
        assert data["sector"] == "Technology"

    async def test_analyst_valuation(self, client, session, valuation_company, valuation_data):
        response = await client.get("/api/v1/companies/MSFT/valuation/analyst")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "MSFT"
        assert data["target_consensus"] == 450.0
        assert data["current_price"] == 400.0
        assert data["upside_pct"] is not None
        assert data["upside_pct"] > 0  # 450 > 400

    async def test_valuation_no_data(self, client, session, valuation_company):
        """Valuation with no financial data should return gracefully."""
        response = await client.get("/api/v1/companies/MSFT/valuation/dcf")
        assert response.status_code == 200
        data = response.json()
        assert data["data_quality"] == "insufficient"
        assert len(data["missing_inputs"]) > 0

    async def test_valuation_company_not_found(self, client, session):
        response = await client.get("/api/v1/companies/ZZZZ/valuation")
        assert response.status_code == 404

    async def test_dcf_scenarios_ordered(self, client, session, valuation_company, valuation_data):
        response = await client.get("/api/v1/companies/MSFT/valuation/dcf")
        data = response.json()
        if len(data["scenarios"]) == 3:
            bear = next(s for s in data["scenarios"] if s["label"] == "bear")
            base = next(s for s in data["scenarios"] if s["label"] == "base")
            bull = next(s for s in data["scenarios"] if s["label"] == "bull")
            assert bear["intrinsic_value_per_share"] <= base["intrinsic_value_per_share"]
            assert base["intrinsic_value_per_share"] <= bull["intrinsic_value_per_share"]

    async def test_analyst_with_price_target(
        self, client, session, valuation_company, valuation_data
    ):
        response = await client.get("/api/v1/companies/MSFT/valuation/analyst")
        data = response.json()
        assert data["target_high"] == 500.0
        assert data["target_low"] == 350.0
        assert data["upside_potential_pct"] is not None
        assert data["downside_risk_pct"] is not None

    async def test_full_valuation_composite(
        self, client, session, valuation_company, valuation_data
    ):
        response = await client.get("/api/v1/companies/MSFT/valuation")
        data = response.json()
        assert data["composite_assessment"] in (
            "undervalued",
            "overvalued",
            "fairly_valued",
            "unavailable",
        )
