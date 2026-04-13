"""LLM 客户端测试."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ainews.config.settings import LLMConfig
from ainews.llm.client import (
    LLMClient,
    LLMClientError,
    LLMResponseParseError,
    parse_json_response,
)


class TestParseJsonResponse:
    """parse_json_response 辅助函数测试."""

    def test_parse_pure_json(self) -> None:
        raw = '{"category": "industry", "relevance": 8}'
        result = parse_json_response(raw)
        assert result == {"category": "industry", "relevance": 8}

    def test_parse_json_with_markdown_code_block(self) -> None:
        raw = '```json\n{"category": "industry", "relevance": 8}\n```'
        result = parse_json_response(raw)
        assert result == {"category": "industry", "relevance": 8}

    def test_parse_json_with_code_block_no_language(self) -> None:
        raw = '```\n{"category": "industry"}\n```'
        result = parse_json_response(raw)
        assert result == {"category": "industry"}

    def test_parse_json_with_whitespace(self) -> None:
        raw = '  \n  {"category": "tools"}  \n  '
        result = parse_json_response(raw)
        assert result == {"category": "tools"}

    def test_parse_json_with_surrounding_text(self) -> None:
        raw = 'Here is the result:\n```json\n{"category": "research"}\n```\nDone.'
        result = parse_json_response(raw)
        assert result == {"category": "research"}

    def test_parse_invalid_json_raises(self) -> None:
        raw = "not json at all"
        with pytest.raises(LLMResponseParseError):
            parse_json_response(raw)

    def test_parse_non_dict_raises(self) -> None:
        raw = '[1, 2, 3]'
        with pytest.raises(LLMResponseParseError, match="不是 dict"):
            parse_json_response(raw)

    def test_parse_empty_string_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_json_response("")


class TestLLMClient:
    """LLMClient 测试."""

    def _make_config(self, **overrides: object) -> LLMConfig:
        defaults = {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "model": "gpt-4o",
            "max_tokens": 1024,
        }
        defaults.update(overrides)
        return LLMConfig(**defaults)  # type: ignore[arg-type]

    def test_call_success(self) -> None:
        config = self._make_config()
        client = LLMClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}]
        }

        with patch.object(client._client, "post", return_value=mock_response):
            result = client.call("test prompt")

        assert result == "Hello world"
        client.close()

    def test_call_authentication_error_not_retryable(self) -> None:
        config = self._make_config()
        client = LLMClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(LLMClientError, match="认证失败"):
                client.call("test prompt")

        client.close()

    def test_call_bad_request_not_retryable(self) -> None:
        config = self._make_config()
        client = LLMClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(LLMClientError, match="请求错误"):
                client.call("test prompt")

        client.close()

    @patch("ainews.llm.client.time.sleep")
    def test_call_retry_on_rate_limit(self, mock_sleep: MagicMock) -> None:
        config = self._make_config()
        client = LLMClient(config)

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.text = "Rate Limited"

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "choices": [{"message": {"content": "Success"}}]
        }

        with patch.object(
            client._client, "post", side_effect=[rate_limit_resp, success_resp]
        ):
            result = client.call("test prompt")

        assert result == "Success"
        mock_sleep.assert_called_once()
        client.close()

    @patch("ainews.llm.client.time.sleep")
    def test_call_retry_exhausted(self, mock_sleep: MagicMock) -> None:
        config = self._make_config()
        client = LLMClient(config)

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.text = "Rate Limited"

        with patch.object(
            client._client, "post", return_value=rate_limit_resp
        ):
            with pytest.raises(LLMClientError, match="重试耗尽"):
                client.call("test prompt")

        assert mock_sleep.call_count == 2  # 3 attempts, 2 sleeps
        client.close()

    @patch("ainews.llm.client.time.sleep")
    def test_call_retry_on_server_error(self, mock_sleep: MagicMock) -> None:
        config = self._make_config()
        client = LLMClient(config)

        server_error_resp = MagicMock()
        server_error_resp.status_code = 500
        server_error_resp.text = "Internal Server Error"

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }

        with patch.object(
            client._client, "post", side_effect=[server_error_resp, success_resp]
        ):
            result = client.call("test prompt")

        assert result == "OK"
        client.close()

    def test_call_malformed_response(self) -> None:
        config = self._make_config()
        client = LLMClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "no choices"}

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(LLMClientError, match="响应格式异常"):
                client.call("test prompt")

        client.close()
