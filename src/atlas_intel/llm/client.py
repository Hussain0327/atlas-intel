"""Lazy-loaded Anthropic AsyncAnthropic singleton."""

from typing import Any


class LLMUnavailableError(Exception):
    """Raised when the Anthropic API key is not configured."""


_client: Any | None = None


def get_client() -> Any:
    """Return a lazy-loaded AsyncAnthropic client singleton.

    Raises LLMUnavailableError if ANTHROPIC_API_KEY is not set.
    """
    global _client

    if _client is not None:
        return _client

    from atlas_intel.config import settings

    if not settings.anthropic_api_key:
        raise LLMUnavailableError("ANTHROPIC_API_KEY is not configured. Set it in your .env file.")

    import anthropic

    _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client
