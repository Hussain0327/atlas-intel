"""OpenAI provider (GPT-4o, GPT-4o-mini, etc.)."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast

from atlas_intel.llm.providers.base import LLMProvider, LLMResponse, ToolCall


class OpenAIProvider(LLMProvider):
    """Wraps ``openai.AsyncOpenAI``."""

    def __init__(self, api_key: str, model: str) -> None:
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return self._model

    # ── Generation ────────────────────────────────────────────────────────

    async def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> LLMResponse:
        oai_messages = self._prepend_system(system, messages)
        response = await self._client.chat.completions.create(
            model=model or self._model,
            max_tokens=max_tokens,
            messages=oai_messages,  # type: ignore[arg-type]
        )
        return self._parse(response)

    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> LLMResponse:
        oai_messages = self._prepend_system(system, messages)
        oai_tools = self._convert_tools(tools)
        response = await self._client.chat.completions.create(
            model=model or self._model,
            max_tokens=max_tokens,
            messages=oai_messages,  # type: ignore[arg-type]
            tools=oai_tools,  # type: ignore[arg-type]
        )
        return self._parse(response)

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        oai_messages = self._prepend_system(system, messages)
        raw = await self._client.chat.completions.create(
            model=model or self._model,
            max_tokens=max_tokens,
            messages=oai_messages,  # type: ignore[arg-type]
            stream=True,
        )
        stream = cast(Any, raw)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    # ── Message history ───────────────────────────────────────────────────

    def build_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": response.text or None}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input),
                    },
                }
                for tc in response.tool_calls
            ]
        return msg

    def build_tool_results_messages(
        self,
        results: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        # OpenAI requires one message per tool result.
        return [
            {"role": "tool", "tool_call_id": tool_call_id, "content": result_str}
            for tool_call_id, result_str in results
        ]

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _prepend_system(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"role": "system", "content": system}, *messages]

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Canonical (Anthropic) format → OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    @staticmethod
    def _parse(response: Any) -> LLMResponse:
        choice = response.choices[0] if response.choices else None
        if not choice:
            return LLMResponse()

        message = choice.message
        text = message.content or ""

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))

        stop = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop = "tool_use"
        elif choice.finish_reason == "length":
            stop = "max_tokens"

        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop)
