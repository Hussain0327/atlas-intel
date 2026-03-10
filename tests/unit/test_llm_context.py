"""Unit tests for LLM context gathering and serialization."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas_intel.llm.context import (
    context_to_json,
    gather_company_context,
    gather_comparison_context,
)
from atlas_intel.schemas.report import CompanyContext, SectorContext


@pytest.fixture
def mock_session():
    return AsyncMock()


SVC = "atlas_intel.services"
CTX = "atlas_intel.llm.context"


class TestGatherCompanyContext:
    async def test_basic_context_gathering(self, mock_session):
        """Test that context is assembled with minimal data."""
        mock_detail = {
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "US",
            "exchange": "NASDAQ",
            "ceo": "Tim Cook",
            "full_time_employees": 164000,
            "description": "Apple designs and sells electronics.",
        }

        with (
            patch(
                f"{SVC}.company_service.get_company_detail",
                new_callable=AsyncMock,
                return_value=mock_detail,
            ),
            patch(
                f"{SVC}.valuation_service.compute_full_valuation_cached",
                new_callable=AsyncMock,
                return_value=MagicMock(model_dump=lambda: {"ticker": "AAPL"}),
            ),
            patch(
                f"{SVC}.fusion_service.compute_sentiment_signal",
                new_callable=AsyncMock,
                return_value=MagicMock(model_dump=lambda: {"score": 0.5}),
            ),
            patch(
                f"{SVC}.fusion_service.compute_growth_signal",
                new_callable=AsyncMock,
                return_value=MagicMock(model_dump=lambda: {"score": 0.3}),
            ),
            patch(
                f"{SVC}.fusion_service.compute_risk_signal",
                new_callable=AsyncMock,
                return_value=MagicMock(model_dump=lambda: {"score": -0.2}),
            ),
            patch(
                f"{SVC}.fusion_service.compute_smart_money_signal",
                new_callable=AsyncMock,
                return_value=MagicMock(model_dump=lambda: {"score": 0.1}),
            ),
            patch(
                f"{SVC}.anomaly_service.detect_all_anomalies_cached",
                new_callable=AsyncMock,
                return_value=MagicMock(model_dump=lambda: {"total": 2}),
            ),
            patch(
                f"{SVC}.financial_service.get_financial_summary",
                new_callable=AsyncMock,
                return_value=[{"year": 2024, "revenue": 400e9}],
            ),
            patch(
                f"{SVC}.price_service.get_price_analytics_cached",
                new_callable=AsyncMock,
                return_value={"current_price": 190.0},
            ),
            patch(
                f"{SVC}.transcript_service.get_sentiment_trend",
                new_callable=AsyncMock,
                return_value=[{"quarter": "Q1 2024", "score": 0.6}],
            ),
            patch(
                f"{SVC}.news_service.get_news",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                f"{SVC}.insider_service.get_insider_sentiment",
                new_callable=AsyncMock,
                return_value={"net_ratio": 0.3},
            ),
            patch(
                f"{SVC}.macro_service.get_macro_summary",
                new_callable=AsyncMock,
                return_value={"GDP": {"latest": 2.5}},
            ),
        ):
            ctx = await gather_company_context(mock_session, 1, "AAPL")

        assert ctx.ticker == "AAPL"
        assert ctx.name == "Apple Inc."
        assert ctx.sector == "Technology"
        assert ctx.ceo == "Tim Cook"
        assert "sentiment" in ctx.signals

    async def test_context_with_missing_data(self, mock_session):
        """Test graceful degradation when services fail."""
        with patch(
            f"{SVC}.company_service.get_company_detail",
            new_callable=AsyncMock,
            side_effect=Exception("DB down"),
        ):
            ctx = await gather_company_context(
                mock_session,
                1,
                "AAPL",
                include_valuation=False,
                include_signals=False,
                include_anomalies=False,
                include_financials=False,
                include_alt_data=False,
            )

        assert ctx.ticker == "AAPL"
        assert ctx.name == "AAPL"  # Fallback to ticker
        assert ctx.signals == {}


class TestGatherComparisonContext:
    async def test_parallel_gathering(self, mock_session):
        """Test that comparison context gathers for multiple companies."""
        with patch(
            f"{CTX}.gather_company_context",
            new_callable=AsyncMock,
            side_effect=lambda s, cid, t, **kw: CompanyContext(ticker=t, name=f"Company {t}"),
        ):
            contexts = await gather_comparison_context(mock_session, [(1, "AAPL"), (2, "MSFT")])

        assert len(contexts) == 2
        assert contexts[0].ticker == "AAPL"
        assert contexts[1].ticker == "MSFT"


class TestContextSerialization:
    def test_company_context_to_json(self):
        ctx = CompanyContext(ticker="AAPL", name="Apple Inc.", sector="Technology")
        result = context_to_json(ctx)
        parsed = json.loads(result)
        assert parsed["ticker"] == "AAPL"
        assert parsed["name"] == "Apple Inc."

    def test_list_context_to_json(self):
        contexts = [
            CompanyContext(ticker="AAPL", name="Apple"),
            CompanyContext(ticker="MSFT", name="Microsoft"),
        ]
        result = context_to_json(contexts)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["ticker"] == "AAPL"

    def test_sector_context_to_json(self):
        ctx = SectorContext(sector="Technology", companies=[{"ticker": "AAPL"}])
        result = context_to_json(ctx)
        parsed = json.loads(result)
        assert parsed["sector"] == "Technology"
