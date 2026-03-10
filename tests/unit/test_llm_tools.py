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
        assert len(names) == 10


class TestExecuteTool:
    async def test_get_company(self, mock_session):
        with patch(
            f"{SVC}.company_service.get_company_detail",
            new_callable=AsyncMock,
            return_value={"name": "Apple", "ticker": "AAPL"},
        ):
            result = await execute_tool(
                mock_session, "get_company", {"identifier": "AAPL"}
            )

        parsed = json.loads(result)
        assert parsed["name"] == "Apple"

    async def test_get_company_not_found(self, mock_session):
        with patch(
            f"{SVC}.company_service.get_company_detail",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_tool(
                mock_session, "get_company", {"identifier": "UNKNOWN"}
            )

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
            result = await execute_tool(
                mock_session, "get_company", {"identifier": "AAPL"}
            )

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
            result = await execute_tool(
                mock_session, "get_signals", {"identifier": "AAPL"}
            )

        parsed = json.loads(result)
        assert "sentiment" in parsed
        assert "growth" in parsed
