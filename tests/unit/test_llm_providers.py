"""Unit tests for the LLM provider abstraction layer."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from atlas_intel.llm.providers.base import LLMResponse, ToolCall


class TestLLMResponse:
    def test_defaults(self):
        r = LLMResponse()
        assert r.text == ""
        assert r.tool_calls == []
        assert r.stop_reason == "end_turn"
        assert r._raw is None

    def test_with_tool_calls(self):
        tc = ToolCall(id="tc_1", name="get_company", input={"ticker": "AAPL"})
        r = LLMResponse(text="", tool_calls=[tc], stop_reason="tool_use")
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0].name == "get_company"


class TestAnthropicProvider:
    def _make_provider(self):
        with patch("anthropic.AsyncAnthropic"):
            from atlas_intel.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(api_key="test-key", model="claude-test")

    def test_name(self):
        p = self._make_provider()
        assert p.name == "anthropic"

    def test_default_model(self):
        p = self._make_provider()
        assert p.default_model == "claude-test"

    async def test_generate(self):
        p = self._make_provider()

        mock_block = MagicMock()
        mock_block.text = "Hello world"
        mock_block.type = "text"

        mock_message = MagicMock()
        mock_message.content = [mock_block]
        mock_message.stop_reason = "end_turn"

        p._client.messages.create = AsyncMock(return_value=mock_message)

        result = await p.generate(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=100,
        )
        assert result.text == "Hello world"
        assert result.stop_reason == "end_turn"

    async def test_generate_with_tools(self):
        p = self._make_provider()

        mock_text = MagicMock()
        mock_text.text = ""
        mock_text.type = "text"

        mock_tool = MagicMock(spec=["type", "id", "name", "input"])
        mock_tool.type = "tool_use"
        mock_tool.id = "tc_1"
        mock_tool.name = "get_company"
        mock_tool.input = {"ticker": "AAPL"}

        mock_message = MagicMock()
        mock_message.content = [mock_text, mock_tool]
        mock_message.stop_reason = "tool_use"

        p._client.messages.create = AsyncMock(return_value=mock_message)

        result = await p.generate_with_tools(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Get AAPL"}],
            tools=[{"name": "get_company", "description": "Get company", "input_schema": {}}],
            max_tokens=100,
        )
        assert result.stop_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_company"

    def test_build_assistant_message(self):
        p = self._make_provider()
        raw_content = [MagicMock()]
        response = LLMResponse(text="test", _raw=raw_content)
        msg = p.build_assistant_message(response)
        assert msg["role"] == "assistant"
        assert msg["content"] is raw_content

    def test_build_tool_results_messages(self):
        p = self._make_provider()
        results = [("tc_1", '{"data": 1}'), ("tc_2", '{"data": 2}')]
        msgs = p.build_tool_results_messages(results)
        # Anthropic bundles into one user message
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert len(msgs[0]["content"]) == 2
        assert msgs[0]["content"][0]["type"] == "tool_result"
        assert msgs[0]["content"][0]["tool_use_id"] == "tc_1"


class TestOpenAIProvider:
    def _make_provider(self):
        with patch("openai.AsyncOpenAI"):
            from atlas_intel.llm.providers.openai import OpenAIProvider

            return OpenAIProvider(api_key="test-key", model="gpt-4o-test")

    def test_name(self):
        p = self._make_provider()
        assert p.name == "openai"

    def test_default_model(self):
        p = self._make_provider()
        assert p.default_model == "gpt-4o-test"

    async def test_generate(self):
        p = self._make_provider()

        mock_message = MagicMock()
        mock_message.content = "Hello from GPT"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        p._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await p.generate(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=100,
        )
        assert result.text == "Hello from GPT"
        assert result.stop_reason == "end_turn"

    async def test_generate_with_tools(self):
        p = self._make_provider()

        mock_fn = MagicMock()
        mock_fn.name = "get_company"
        mock_fn.arguments = json.dumps({"ticker": "AAPL"})

        mock_tc = MagicMock()
        mock_tc.id = "call_1"
        mock_tc.function = mock_fn

        mock_message = MagicMock()
        mock_message.content = ""
        mock_message.tool_calls = [mock_tc]

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        p._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await p.generate_with_tools(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Get AAPL"}],
            tools=[{"name": "get_company", "description": "Get company", "input_schema": {}}],
            max_tokens=100,
        )
        assert result.stop_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_company"
        assert result.tool_calls[0].input == {"ticker": "AAPL"}

    def test_build_assistant_message_text_only(self):
        p = self._make_provider()
        response = LLMResponse(text="Hello")
        msg = p.build_assistant_message(response)
        assert msg["role"] == "assistant"
        assert msg["content"] == "Hello"
        assert "tool_calls" not in msg

    def test_build_assistant_message_with_tools(self):
        p = self._make_provider()
        tc = ToolCall(id="call_1", name="get_company", input={"ticker": "AAPL"})
        response = LLMResponse(text="", tool_calls=[tc])
        msg = p.build_assistant_message(response)
        assert msg["role"] == "assistant"
        assert len(msg["tool_calls"]) == 1
        assert msg["tool_calls"][0]["type"] == "function"
        assert msg["tool_calls"][0]["function"]["name"] == "get_company"

    def test_build_tool_results_messages(self):
        p = self._make_provider()
        results = [("call_1", '{"data": 1}'), ("call_2", '{"data": 2}')]
        msgs = p.build_tool_results_messages(results)
        # OpenAI uses one message per tool result
        assert len(msgs) == 2
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "call_1"
        assert msgs[1]["tool_call_id"] == "call_2"

    def test_convert_tools(self):
        from atlas_intel.llm.providers.openai import OpenAIProvider

        tools = [
            {
                "name": "get_company",
                "description": "Look up company info",
                "input_schema": {
                    "type": "object",
                    "properties": {"ticker": {"type": "string"}},
                    "required": ["ticker"],
                },
            }
        ]
        converted = OpenAIProvider._convert_tools(tools)
        assert len(converted) == 1
        assert converted[0]["type"] == "function"
        assert converted[0]["function"]["name"] == "get_company"
        assert converted[0]["function"]["parameters"]["type"] == "object"


class TestProviderRegistry:
    def setup_method(self):
        from atlas_intel.llm.client import reset_providers

        reset_providers()

    def teardown_method(self):
        from atlas_intel.llm.client import reset_providers

        reset_providers()

    def test_no_keys_raises(self):
        import pytest

        from atlas_intel.llm.client import get_provider

        with patch("atlas_intel.config.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            mock_settings.openai_api_key = ""
            mock_settings.llm_provider = "auto"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            with pytest.raises(Exception, match="No LLM provider"):
                get_provider()

    def test_anthropic_only(self):
        from atlas_intel.llm.client import get_provider

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("anthropic.AsyncAnthropic"),
        ):
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.openai_api_key = ""
            mock_settings.llm_provider = "auto"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            provider = get_provider()
            assert provider.name == "anthropic"

    def test_openai_only(self):
        from atlas_intel.llm.client import get_provider

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("openai.AsyncOpenAI"),
        ):
            mock_settings.anthropic_api_key = ""
            mock_settings.openai_api_key = "sk-openai-test"
            mock_settings.llm_provider = "auto"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            provider = get_provider()
            assert provider.name == "openai"

    def test_dual_auto_prefers_anthropic(self):
        from atlas_intel.llm.client import get_provider

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("anthropic.AsyncAnthropic"),
            patch("openai.AsyncOpenAI"),
        ):
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.openai_api_key = "sk-openai-test"
            mock_settings.llm_provider = "auto"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            provider = get_provider()
            assert provider.name == "anthropic"

    def test_dual_force_openai(self):
        from atlas_intel.llm.client import get_provider

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("anthropic.AsyncAnthropic"),
            patch("openai.AsyncOpenAI"),
        ):
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.openai_api_key = "sk-openai-test"
            mock_settings.llm_provider = "openai"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            provider = get_provider()
            assert provider.name == "openai"

    def test_prefer_overrides_config(self):
        from atlas_intel.llm.client import get_provider

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("anthropic.AsyncAnthropic"),
            patch("openai.AsyncOpenAI"),
        ):
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.openai_api_key = "sk-openai-test"
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            provider = get_provider(prefer="openai")
            assert provider.name == "openai"

    def test_failover_when_preferred_unavailable(self):
        from atlas_intel.llm.client import get_provider

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("openai.AsyncOpenAI"),
        ):
            mock_settings.anthropic_api_key = ""
            mock_settings.openai_api_key = "sk-openai-test"
            mock_settings.llm_provider = "anthropic"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            # Requested anthropic but only openai available — failover
            provider = get_provider()
            assert provider.name == "openai"

    def test_get_client_backward_compat(self):
        from atlas_intel.llm.client import get_client

        with (
            patch("atlas_intel.config.settings") as mock_settings,
            patch("anthropic.AsyncAnthropic"),
        ):
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.openai_api_key = ""
            mock_settings.llm_provider = "auto"
            mock_settings.anthropic_model = "claude-test"
            mock_settings.openai_model = "gpt-test"

            client = get_client()
            assert client is not None
