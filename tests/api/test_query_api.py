"""API tests for natural language query endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from atlas_intel.schemas.report import QueryResponse

SVC = "atlas_intel.services"


class TestQueryEndpoint:
    async def test_query_success(self, client):
        mock_response = QueryResponse(
            query="What is AAPL's PE ratio?",
            answer="Apple's PE ratio is 30.5.",
            tools_used=["get_company"],
            generated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        with patch(
            f"{SVC}.query_service.process_natural_language_query",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            resp = await client.post(
                "/api/v1/query",
                json={"query": "What is AAPL's PE ratio?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Apple's PE ratio is 30.5."
        assert "get_company" in data["tools_used"]

    async def test_query_empty(self, client):
        resp = await client.post("/api/v1/query", json={"query": ""})
        assert resp.status_code == 422

    async def test_query_llm_unavailable(self, client):
        from atlas_intel.llm.client import LLMUnavailableError

        with patch(
            f"{SVC}.query_service.process_natural_language_query",
            new_callable=AsyncMock,
            side_effect=LLMUnavailableError("No API key"),
        ):
            resp = await client.post(
                "/api/v1/query",
                json={"query": "Tell me about AAPL"},
            )

        assert resp.status_code == 503
