"""LLM 客户端：基于 Anthropic Messages API 协议封装."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from ainews.config.settings import LLMConfig

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
ANTHROPIC_VERSION = "2023-06-01"


class LLMClientError(Exception):
    """LLM 客户端错误."""


class LLMResponseParseError(Exception):
    """LLM 响应 JSON 解析错误."""


class LLMClient:
    """LLM 客户端，使用 Anthropic Messages API 协议."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._base_url = config.base_url
        self._api_key = config.api_key
        self._model = config.model
        self._max_tokens = config.max_tokens
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def call(self, prompt: str) -> str:
        """发送单条用户消息到 LLM 并返回文本响应.

        内置指数退避重试（最多 3 次），可重试的错误包括：
        429 (Rate Limit)、5xx (Server Error)、网络超时/连接错误。
        认证错误 (401/403) 和请求错误 (400) 不可重试。

        Args:
            prompt: 用户消息文本

        Returns:
            LLM 响应文本

        Raises:
            LLMClientError: 重试耗尽或不可重试错误
        """
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                return self._do_call(prompt)
            except _RetryableError as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        "LLM 调用失败 (第 %d 次)，%.1fs 后重试: %s",
                        attempt + 1,
                        backoff,
                        exc,
                    )
                    time.sleep(backoff)
            except _NonRetryableError as exc:
                raise LLMClientError(str(exc)) from exc

        msg = f"LLM 调用重试耗尽 ({MAX_RETRIES} 次): {last_error}"
        raise LLMClientError(msg)

    def _do_call(self, prompt: str) -> str:
        """执行单次 API 调用."""
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self._client.post("/v1/messages", json=payload)

        if response.status_code == 401 or response.status_code == 403:
            raise _NonRetryableError(
                f"认证失败 (HTTP {response.status_code}): {response.text}"
            )
        if response.status_code == 400:
            raise _NonRetryableError(
                f"请求错误 (HTTP 400): {response.text}"
            )
        if response.status_code == 429:
            raise _RetryableError(
                f"速率限制 (HTTP 429): {response.text}"
            )
        if response.status_code >= 500:
            raise _RetryableError(
                f"服务端错误 (HTTP {response.status_code}): {response.text}"
            )
        if response.status_code != 200:
            raise _NonRetryableError(
                f"未知错误 (HTTP {response.status_code}): {response.text}"
            )

        data = response.json()
        try:
            content_blocks = data["content"]
            text_parts = [
                block["text"] for block in content_blocks if block["type"] == "text"
            ]
            return "\n".join(text_parts)
        except (KeyError, IndexError) as exc:
            raise _NonRetryableError(
                f"响应格式异常: {json.dumps(data, ensure_ascii=False)}"
            ) from exc

    def close(self) -> None:
        """关闭 HTTP 客户端."""
        self._client.close()


class _RetryableError(Exception):
    """可重试的错误."""


class _NonRetryableError(Exception):
    """不可重试的错误."""


def parse_json_response(raw: str) -> dict[str, Any]:
    """从 LLM 响应文本中提取 JSON.

    支持纯 JSON 文本和 markdown code block 包裹的 JSON.
    自动清理 JSON 字符串值中的非法控制字符.

    Args:
        raw: LLM 原始响应文本

    Returns:
        解析后的 Python dict

    Raises:
        LLMResponseParseError: 解析失败
    """
    text = raw.strip()

    # 尝试提取 markdown code block 中的 JSON
    code_block_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL
    )
    if code_block_match:
        json_text = code_block_match.group(1).strip()
    else:
        json_text = text

    # 清理非法控制字符（包括 JSON 字符串值中的字面换行符）
    # 移除所有 0x00-0x1F 控制字符；已转义的 \n \r \t 等不受影响（它们是 \ + 字母）
    json_text = re.sub(r'[\x00-\x1f]', '', json_text)

    try:
        result = json.loads(json_text)
        if isinstance(result, dict):
            return result
        msg = f"JSON 结果不是 dict: {type(result).__name__}"
        raise LLMResponseParseError(msg)
    except json.JSONDecodeError as exc:
        raise LLMResponseParseError(
            f"JSON 解析失败: {exc}\n原始响应: {raw}"
        ) from exc
