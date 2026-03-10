"""LLM provider registry with lazy initialization and failover.

Supports dual-provider architecture (Anthropic Claude + OpenAI GPT).
Provider selection: ``llm_provider`` config controls routing —
``"auto"`` picks the first available, ``"anthropic"``/``"openai"`` force a specific one.
"""

import logging
from typing import Any

from atlas_intel.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when no LLM provider is available."""


_providers: dict[str, LLMProvider] = {}
_initialized = False


def _init_providers() -> None:
    """Lazily initialize all providers with configured API keys."""
    global _initialized
    if _initialized:
        return

    from atlas_intel.config import settings

    if settings.anthropic_api_key:
        from atlas_intel.llm.providers.anthropic import AnthropicProvider

        _providers["anthropic"] = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
        logger.info("Anthropic provider initialized (model=%s)", settings.anthropic_model)

    if settings.openai_api_key:
        from atlas_intel.llm.providers.openai import OpenAIProvider

        _providers["openai"] = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        logger.info("OpenAI provider initialized (model=%s)", settings.openai_model)

    _initialized = True


def get_provider(prefer: str | None = None) -> LLMProvider:
    """Return the best available LLM provider.

    Args:
        prefer: Override the config-level ``llm_provider`` setting for this call.
                Use ``"anthropic"`` or ``"openai"`` to force a specific provider.

    Returns:
        An initialized ``LLMProvider`` instance.

    Raises:
        LLMUnavailableError: If no provider is available (no API keys configured).

    Selection logic:
        1. If ``prefer`` (or ``settings.llm_provider``) is a specific provider name,
           try that first, then failover to the other.
        2. If ``"auto"``, try Anthropic first, then OpenAI.
    """
    _init_providers()

    if not _providers:
        raise LLMUnavailableError(
            "No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env."
        )

    from atlas_intel.config import settings

    choice = prefer or settings.llm_provider

    if choice in _providers:
        return _providers[choice]

    # "auto" or requested provider not available → return first available
    # Priority: anthropic > openai (for consistency with existing behavior)
    for name in ("anthropic", "openai"):
        if name in _providers:
            if choice not in ("auto", name):
                logger.warning(
                    "Requested provider %r unavailable, failing over to %r", choice, name
                )
            return _providers[name]

    raise LLMUnavailableError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env."
    )


def reset_providers() -> None:
    """Clear cached providers. Used in tests."""
    global _initialized
    _providers.clear()
    _initialized = False


# Backward compatibility — old code imports get_client from here.
# Callers should migrate to get_provider().
def get_client() -> Any:
    """Legacy: return the raw Anthropic AsyncAnthropic client.

    .. deprecated:: Use ``get_provider()`` instead.
    """
    _init_providers()
    if "anthropic" in _providers:
        return _providers["anthropic"]._client  # type: ignore[attr-defined]

    raise LLMUnavailableError("ANTHROPIC_API_KEY is not configured. Set it in your .env file.")
