"""API tests for analyst endpoints."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.models.analyst_estimate import AnalystEstimate
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.company import Company
from atlas_intel.models.price_target import PriceTarget


@pytest.fixture
async def seeded_analyst(session):
    company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(company)
    await session.flush()

    estimates = [
        AnalystEstimate(
            company_id=company.id,
            period="annual",
            estimate_date=date(2024, 9, 30),
            estimated_revenue_avg=Decimal("394500000000"),
            estimated_eps_avg=Decimal("6.58"),
        ),
        AnalystEstimate(
            company_id=company.id,
            period="quarter",
            estimate_date=date(2024, 3, 31),
            estimated_revenue_avg=Decimal("95000000000"),
            estimated_eps_avg=Decimal("1.50"),
        ),
    ]

    grades = [
        AnalystGrade(
            company_id=company.id,
            grade_date=date(2024, 1, 26),
            grading_company="Morgan Stanley",
            new_grade="Overweight",
            action="upgrade",
        ),
        AnalystGrade(
            company_id=company.id,
            grade_date=date(2024, 1, 15),
            grading_company="Barclays",
            new_grade="Equal-Weight",
            action="downgrade",
        ),
    ]

    target = PriceTarget(
        company_id=company.id,
        target_high=Decimal("250.00"),
        target_low=Decimal("160.00"),
        target_consensus=Decimal("210.00"),
        target_median=Decimal("215.00"),
    )

    session.add_all(estimates + grades + [target])
    await session.commit()
    return company


class TestAnalystAPI:
    async def test_list_estimates(self, client, seeded_analyst):
        resp = await client.get("/api/v1/companies/AAPL/analyst/estimates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_estimates_period_filter(self, client, seeded_analyst):
        resp = await client.get(
            "/api/v1/companies/AAPL/analyst/estimates", params={"period": "annual"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["period"] == "annual"

    async def test_list_grades(self, client, seeded_analyst):
        resp = await client.get("/api/v1/companies/AAPL/analyst/grades")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_price_target(self, client, seeded_analyst):
        resp = await client.get("/api/v1/companies/AAPL/analyst/price-target")
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_consensus"] == "210.0000"

    async def test_price_target_none(self, client, session):
        """Returns 404 when no price target exists for the company."""
        company = Company(cik=12345, ticker="NOPT", name="No Price Target Inc.")
        session.add(company)
        await session.commit()

        resp = await client.get("/api/v1/companies/NOPT/analyst/price-target")
        assert resp.status_code == 404

    async def test_consensus(self, client, seeded_analyst):
        resp = await client.get("/api/v1/companies/AAPL/analyst/consensus")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "target_consensus" in data
        assert "grade_distribution" in data
        assert "sentiment" in data

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/analyst/estimates")
        assert resp.status_code == 404

    async def test_grades_not_found(self, client):
        resp = await client.get("/api/v1/companies/ZZZZ/analyst/grades")
        assert resp.status_code == 404
