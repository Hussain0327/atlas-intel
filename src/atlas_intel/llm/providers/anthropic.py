"""Anthropic Claude provider."""

from collections.abc import AsyncIterator
from typing import Any

from atlas_intel.llm.providers.base import LLMProvider, LLMResponse, ToolCall


class AnthropicProvider(LLMProvider):
    """Wraps ``anthropic.AsyncAnthropic``."""

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "anthropic"

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
        message = await self._client.messages.create(
            model=model or self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        )
        return self._parse(message)

    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> LLMResponse:
        message = await self._client.messages.create(
            model=model or self._model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,  # type: ignore[arg-type]
            messages=messages,  # type: ignore[arg-type]
        )
        return self._parse(message)

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=model or self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ── Message history ───────────────────────────────────────────────────

    def build_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        # Pass through raw SDK content blocks — the Anthropic SDK accepts them.
        return {"role": "assistant", "content": response._raw}

    def build_tool_results_messages(
        self,
        results: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        # Anthropic bundles all tool results into one user message.
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": result_str,
                    }
                    for tool_call_id, result_str in results
                ],
            }
        ]

    # ── Internal ──────────────────────────────────────────────────────────

    def _parse(self, message: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in message.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        stop = "end_turn"
        if message.stop_reason == "tool_use":
            stop = "tool_use"
        elif message.stop_reason == "max_tokens":
            stop = "max_tokens"

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop,
            _raw=message.content,
        )
