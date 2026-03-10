"""Natural language query service with tool-use loop."""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.config import settings
from atlas_intel.llm.client import get_client
from atlas_intel.llm.prompts import NL_QUERY_SYSTEM_PROMPT
from atlas_intel.llm.tools import TOOL_DEFINITIONS, execute_tool
from atlas_intel.schemas.report import QueryResponse

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


async def process_natural_language_query(
    session: AsyncSession,
    query: str,
) -> QueryResponse:
    """Process a natural language query using Claude tool-use loop."""
    client = get_client()
    tools_used: list[str] = []

    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            system=NL_QUERY_SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            answer = ""
            for block in response.content:
                if hasattr(block, "text"):
                    answer += block.text
            return QueryResponse(
                query=query,
                answer=answer,
                tools_used=tools_used,
                generated_at=datetime.now(UTC).replace(tzinfo=None),
            )

        if response.stop_reason == "tool_use":
            # Process tool calls
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_used.append(block.name)
                    result_str = await execute_tool(session, block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # If we hit max iterations, extract whatever text we have
    answer = ""
    for block in response.content:
        if hasattr(block, "text"):
            answer += block.text

    return QueryResponse(
        query=query,
        answer=answer or "I was unable to fully answer the query within the iteration limit.",
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
    client = get_client()
    tools_used: list[str] = []

    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    # Non-streaming tool-use loop
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            system=NL_QUERY_SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_used.append(block.name)
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name})}\n\n"
                    result_str = await execute_tool(session, block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Stream final answer
    async with client.messages.stream(
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        system=NL_QUERY_SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'tools_used': tools_used})}\n\n"
