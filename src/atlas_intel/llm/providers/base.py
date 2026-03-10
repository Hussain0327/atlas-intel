"""Abstract LLM provider interface.

Every provider normalizes its SDK's response into LLMResponse / ToolCall so that
service code never touches vendor types directly.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    """Provider-agnostic LLM response.

    Attributes:
        text: Concatenated text output (may be empty when tool_calls are present).
        tool_calls: Tool invocations the model wants to execute.
        stop_reason: Normalized stop reason — "end_turn", "tool_use", or "max_tokens".
        _raw: Provider-specific payload kept for message-history round-tripping.
    """

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    _raw: Any = field(default=None, repr=False)


class LLMProvider(ABC):
    """Contract that every LLM backend must satisfy.

    Message history is opaque to callers — providers build and consume their own
    message formats via ``build_assistant_message`` and ``build_tool_results_messages``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``"anthropic"`` or ``"openai"``."""

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Configured model id for this provider."""

    # ── Generation ────────────────────────────────────────────────────────

    @abstractmethod
    async def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> LLMResponse:
        """Single-turn text generation (no tool use)."""

    @abstractmethod
    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> LLMResponse:
        """Generation with tool-use capability.

        ``tools`` are in canonical (Anthropic) format — the provider converts
        to its native schema internally.
        """

    @abstractmethod
    async def stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield text deltas."""
        raise NotImplementedError  # pragma: no cover
        yield ""  # pragma: no cover  # makes this a valid AsyncIterator for type checkers

    # ── Message history helpers ───────────────────────────────────────────

    @abstractmethod
    def build_assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        """Pack a model response into a message-history entry."""

    @abstractmethod
    def build_tool_results_messages(
        self,
        results: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Pack tool results into message-history entries.

        ``results``: list of ``(tool_call_id, result_json_string)`` pairs.

        Returns a *list* of messages because some providers require one message
        per tool result (OpenAI) while others bundle them (Anthropic).
        """
