"""Unit tests for LLM tool routing."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas_intel.llm.tools import TOOL_DEFINITIONS, execute_tool

SVC = "atlas_intel.services"


@pytest.fixture
def mock_session():
    return AsyncMock()


class TestToolDefinitions:
    def test_all_tools_have_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_expected_tool_names(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        assert "get_company" in names
        assert "screen_companies" in names
        assert "get_signals" in names
        assert "get_valuation" in names
        assert "get_anomalies" in names
        assert "get_financials" in names
        assert "get_prices" in names
        assert "get_news" in names
        assert "get_insider" in names
        assert "get_macro" in names
        assert "get_metrics" in names
        assert "get_analyst_consensus" in names
        assert "get_transcript_sentiment" in names
        assert "get_events" in names
        assert len(names) == 14


class TestExecuteTool:
    async def test_get_company(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        with (
            patch(
                f"{SVC}.company_service.get_company_detail",
                new_callable=AsyncMock,
                return_value={"name": "Apple", "ticker": "AAPL"},
            ),
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.metric_service.get_latest_metrics_cached",
                new_callable=AsyncMock,
                return_value={"pe_ratio": 28.5, "roe": 0.15, "market_cap": 3e12},
            ),
        ):
            result = await execute_tool(mock_session, "get_company", {"identifier": "AAPL"})

        parsed = json.loads(result)
        assert parsed["name"] == "Apple"
        assert parsed["pe_ratio"] == 28.5
        assert parsed["roe"] == 0.15

    async def test_get_company_not_found(self, mock_session):
        with patch(
            f"{SVC}.company_service.get_company_detail",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_tool(mock_session, "get_company", {"identifier": "UNKNOWN"})

        parsed = json.loads(result)
        assert "error" in parsed

    async def test_get_macro(self, mock_session):
        with patch(
            f"{SVC}.macro_service.get_macro_summary",
            new_callable=AsyncMock,
            return_value={"GDP": {"latest": 2.5}},
        ):
            result = await execute_tool(mock_session, "get_macro", {})

        parsed = json.loads(result)
        assert "GDP" in parsed

    async def test_unknown_tool(self, mock_session):
        result = await execute_tool(mock_session, "nonexistent_tool", {})
        parsed = json.loads(result)
        assert "error" in parsed

    async def test_tool_exception_handling(self, mock_session):
        with patch(
            f"{SVC}.company_service.get_company_detail",
            new_callable=AsyncMock,
            side_effect=Exception("DB error"),
        ):
            result = await execute_tool(mock_session, "get_company", {"identifier": "AAPL"})

        parsed = json.loads(result)
        assert "error" in parsed

    async def test_get_signals(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        mock_signal = MagicMock()
        mock_signal.model_dump.return_value = {"score": 0.5, "label": "positive"}

        with (
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.fusion_service.compute_sentiment_signal",
                new_callable=AsyncMock,
                return_value=mock_signal,
            ),
            patch(
                f"{SVC}.fusion_service.compute_growth_signal",
                new_callable=AsyncMock,
                return_value=mock_signal,
            ),
            patch(
                f"{SVC}.fusion_service.compute_risk_signal",
                new_callable=AsyncMock,
                return_value=mock_signal,
            ),
            patch(
                f"{SVC}.fusion_service.compute_smart_money_signal",
                new_callable=AsyncMock,
                return_value=mock_signal,
            ),
        ):
            result = await execute_tool(mock_session, "get_signals", {"identifier": "AAPL"})

        parsed = json.loads(result)
        assert "sentiment" in parsed
        assert "growth" in parsed

    async def test_get_news_includes_snippet(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        mock_article = MagicMock()
        mock_article.title = "Apple Q4"
        mock_article.published_at = "2024-01-01"
        mock_article.source_name = "Reuters"
        mock_article.url = "https://example.com"
        mock_article.snippet = "Apple reported strong Q4 results..."

        with (
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.news_service.get_news",
                new_callable=AsyncMock,
                return_value=([mock_article], 1),
            ),
        ):
            result = await execute_tool(mock_session, "get_news", {"identifier": "AAPL"})

        parsed = json.loads(result)
        assert parsed["articles"][0]["snippet"] == "Apple reported strong Q4 results..."

    async def test_get_metrics(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        with (
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.metric_service.get_latest_metrics_cached",
                new_callable=AsyncMock,
                return_value={"pe_ratio": 28.5, "roe": 0.15},
            ),
        ):
            result = await execute_tool(mock_session, "get_metrics", {"identifier": "AAPL"})

        parsed = json.loads(result)
        assert parsed["pe_ratio"] == 28.5

    async def test_get_analyst_consensus(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        with (
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.analyst_service.get_analyst_consensus_cached",
                new_callable=AsyncMock,
                return_value={"target_high": 250, "target_low": 180},
            ),
        ):
            result = await execute_tool(
                mock_session, "get_analyst_consensus", {"identifier": "AAPL"}
            )

        parsed = json.loads(result)
        assert parsed["target_high"] == 250

    async def test_get_transcript_sentiment(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        with (
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.transcript_service.get_sentiment_trend",
                new_callable=AsyncMock,
                return_value=[{"quarter": 4, "year": 2024, "score": 0.8}],
            ),
            patch(
                f"{SVC}.transcript_service.get_keyword_analysis",
                new_callable=AsyncMock,
                return_value=[{"keyword": "AI", "total_relevance": 5.0}],
            ),
        ):
            result = await execute_tool(
                mock_session, "get_transcript_sentiment", {"identifier": "AAPL"}
            )

        parsed = json.loads(result)
        assert "sentiment_trend" in parsed
        assert "top_keywords" in parsed
        assert parsed["sentiment_trend"][0]["score"] == 0.8

    async def test_get_events(self, mock_session):
        mock_company = MagicMock()
        mock_company.id = 1
        mock_company.ticker = "AAPL"

        with (
            patch(
                f"{SVC}.company_service.get_company_by_identifier",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch(
                f"{SVC}.event_service.get_event_summary",
                new_callable=AsyncMock,
                return_value={"ticker": "AAPL", "total_events": 5},
            ),
        ):
            result = await execute_tool(mock_session, "get_events", {"identifier": "AAPL"})

        parsed = json.loads(result)
        assert parsed["total_events"] == 5
