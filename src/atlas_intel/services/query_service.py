"""Natural language query service with tool-use loop."""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.config import settings
from atlas_intel.llm.client import get_provider
from atlas_intel.llm.prompts import NL_QUERY_SYSTEM_PROMPT
from atlas_intel.llm.tools import TOOL_DEFINITIONS, execute_tool
from atlas_intel.schemas.report import QueryResponse

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


async def process_natural_language_query(
    session: AsyncSession,
    query: str,
) -> QueryResponse:
    """Process a natural language query using LLM tool-use loop."""
    provider = get_provider()
    tools_used: list[str] = []

    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = await provider.generate_with_tools(
            system=NL_QUERY_SYSTEM_PROMPT,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            max_tokens=settings.llm_max_tokens,
        )

        if response.stop_reason == "end_turn":
            return QueryResponse(
                query=query,
                answer=response.text,
                tools_used=tools_used,
                generated_at=datetime.now(UTC).replace(tzinfo=None),
            )

        if response.stop_reason == "tool_use":
            tool_results: list[tuple[str, str]] = []
            for tc in response.tool_calls:
                tools_used.append(tc.name)
                try:
                    result_str = await execute_tool(session, tc.name, tc.input)
                except Exception as exc:
                    result_str = json.dumps({"error": str(exc)})
                tool_results.append((tc.id, result_str))

            messages.append(provider.build_assistant_message(response))
            messages.extend(provider.build_tool_results_messages(tool_results))
        else:
            break

    # If we hit max iterations, extract whatever text we have
    return QueryResponse(
        query=query,
        answer=response.text
        or "I was unable to fully answer the query within the iteration limit.",
        tools_used=tools_used,
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )


async def stream_natural_language_query(
    session: AsyncSession,
    query: str,
) -> AsyncIterator[str]:
    """Stream a natural language query response.

    Note: This performs the tool-use loop non-streaming, then streams the final answer.
    """
    provider = get_provider()
    tools_used: list[str] = []

    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    # Non-streaming tool-use loop
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = await provider.generate_with_tools(
            system=NL_QUERY_SYSTEM_PROMPT,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            max_tokens=settings.llm_max_tokens,
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results: list[tuple[str, str]] = []
            for tc in response.tool_calls:
                tools_used.append(tc.name)
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc.name})}\n\n"
                try:
                    result_str = await execute_tool(session, tc.name, tc.input)
                except Exception as exc:
                    result_str = json.dumps({"error": str(exc)})
                tool_results.append((tc.id, result_str))

            messages.append(provider.build_assistant_message(response))
            messages.extend(provider.build_tool_results_messages(tool_results))
        else:
            break

    # Stream final answer
    async for text in provider.stream(
        system=NL_QUERY_SYSTEM_PROMPT,
        messages=messages,
        max_tokens=settings.llm_max_tokens,
    ):
        yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'tools_used': tools_used})}\n\n"
