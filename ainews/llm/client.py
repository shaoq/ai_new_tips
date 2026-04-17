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
        # 尝试修复常见的 LLM JSON 截断问题
        repaired = _try_repair_json(json_text, exc)
        if repaired is not None:
            logger.warning("JSON 修复成功，原错误: %s", exc)
            return repaired
        raise LLMResponseParseError(
            f"JSON 解析失败: {exc}\n原始响应: {raw}"
        ) from exc


def _try_repair_json(text: str, error: json.JSONDecodeError) -> dict[str, Any] | None:
    """尝试修复 LLM 输出的常见 JSON 问题.

    常见错误模式 (GLM-5 等 LLM):
    - "summary_zh "value"        — 缺少 ": "  (冒号+引号)
    - "summary_zh":unquoted      — 缺少值的开头引号
    - "summary_zh": "truncated   — 值被截断
    - 尾部不完整                   — 缺少闭合括号
    """
    # 已知的 JSON 字段名
    known_keys = [
        "title_zh", "category", "category_confidence",
        "summary_zh", "relevance", "relevance_reason",
        "tags", "entities",
    ]

    working = text

    # 策略1: 对已知字段名，修复 "key "value" → "key": "value"
    # 实际结构: "summary_zh "Anthropic..." 中:
    #   "summary_zh " 是一个完整 JSON 字符串(key含尾部空格)
    #   后面紧跟 "Anthropic" 是 value 的开头(但缺 : 和引号)
    # 修复: 在 "key " 后、value 开始前 插入 ": "
    for key in known_keys:
        # 匹配 "key "X 或 "key "X (key闭合引号后紧跟非逗号非右括号非空白字符)
        pattern = rf'"{re.escape(key)}\s*"([^,\]:\s])'
        if re.search(pattern, working):
            working = re.sub(
                rf'("{re.escape(key)})\s*"([^,\]:\s])',
                rf'\1": "\2',
                working,
            )

    if working != text:
        try:
            result = json.loads(working)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # 策略2: 对已知字段名，修复 "key": unquoted → "key": "unquoted"
    for key in known_keys:
        # 匹配 "key": 后紧跟非引号非数组字符，直到逗号或 }
        closing = r'[,\}]'
        pattern = rf'"{re.escape(key)}"\s*:\s*([^"\[\]{{,}}]+?)\s*({closing})'
        if re.search(pattern, working):
            working = re.sub(
                rf'("{re.escape(key)}"\s*:\s*)([^"\[\]{{,}}]+?)\s*({closing})',
                r'\1"\2"\3',
                working,
            )

    try:
        result = json.loads(working)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 策略3: 尾部截断修复 — 补上缺失的引号和括号
    pos = error.pos if error.pos < len(text) else len(text)
    truncated = text[:pos]

    last_quote = truncated.rfind('"')
    last_comma = truncated.rfind(',')
    last_colon = truncated.rfind(':')
    if last_quote > max(last_comma, last_colon):
        truncated = truncated[:last_quote + 1]

    open_braces = truncated.count('{') - truncated.count('}')
    open_brackets = truncated.count('[') - truncated.count(']')
    truncated += ']' * max(0, open_brackets) + '}' * max(0, open_braces)

    try:
        result = json.loads(truncated)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    return None
