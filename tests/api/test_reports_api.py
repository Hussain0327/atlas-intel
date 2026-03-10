"""API tests for report generation endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from atlas_intel.schemas.report import ReportResponse

SVC = "atlas_intel.services"


@pytest.fixture
def mock_report():
    return ReportResponse(
        ticker="AAPL",
        report_type="comprehensive",
        content="# AAPL Report\n\nThis is a test report.",
        data_context={"signals": {}},
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )


class TestCompanyReport:
    async def test_company_report_success(self, client, session, mock_report):
        from atlas_intel.models.company import Company

        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        with patch(
            f"{SVC}.report_service.generate_company_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            resp = await client.get("/api/v1/companies/AAPL/report")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["report_type"] == "comprehensive"
        assert "test report" in data["content"]

    async def test_company_report_quick(self, client, session, mock_report):
        from atlas_intel.models.company import Company

        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        mock_report.report_type = "quick"
        with patch(
            f"{SVC}.report_service.generate_company_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            resp = await client.get("/api/v1/companies/AAPL/report?report_type=quick")

        assert resp.status_code == 200

    async def test_company_report_not_found(self, client):
        resp = await client.get("/api/v1/companies/UNKNOWN/report")
        assert resp.status_code == 404

    async def test_company_report_llm_unavailable(self, client, session):
        from atlas_intel.llm.client import LLMUnavailableError
        from atlas_intel.models.company import Company

        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()

        with patch(
            f"{SVC}.report_service.generate_company_report",
            new_callable=AsyncMock,
            side_effect=LLMUnavailableError("No API key"),
        ):
            resp = await client.get("/api/v1/companies/AAPL/report")

        assert resp.status_code == 503


class TestComparisonReport:
    async def test_comparison_report(self, client, session, mock_report):
        from atlas_intel.models.company import Company

        session.add(Company(cik=320193, ticker="AAPL", name="Apple Inc."))
        session.add(Company(cik=789019, ticker="MSFT", name="Microsoft Corp."))
        await session.commit()

        mock_report.report_type = "comparison"
        with patch(
            f"{SVC}.report_service.generate_comparison_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            resp = await client.post(
                "/api/v1/reports/comparison",
                json={"tickers": ["AAPL", "MSFT"]},
            )

        assert resp.status_code == 200

    async def test_comparison_too_few_tickers(self, client):
        resp = await client.post(
            "/api/v1/reports/comparison",
            json={"tickers": ["AAPL"]},
        )
        assert resp.status_code == 422

    async def test_comparison_ticker_not_found(self, client, session):
        from atlas_intel.models.company import Company

        session.add(Company(cik=320193, ticker="AAPL", name="Apple Inc."))
        await session.commit()

        resp = await client.post(
            "/api/v1/reports/comparison",
            json={"tickers": ["AAPL", "UNKNOWN"]},
        )
        assert resp.status_code == 404


class TestSectorReport:
    async def test_sector_report(self, client, mock_report):
        mock_report.report_type = "sector"
        with patch(
            f"{SVC}.report_service.generate_sector_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            resp = await client.get("/api/v1/reports/sector/Technology")

        assert resp.status_code == 200
