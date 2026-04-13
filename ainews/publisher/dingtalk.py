"""钉钉 Webhook 客户端：签名认证、HTTP 发送、重试、限流."""

from __future__ import annotations

import hashlib
import hmac
import base64
import logging
import time
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1.1 HMAC-SHA256 签名
# ---------------------------------------------------------------------------

def sign_dingtalk(secret: str) -> tuple[str, str]:
    """计算钉钉机器人签名.

    算法: timestamp + "\\n" + secret -> HMAC-SHA256 -> base64 -> URL encode

    Returns:
        (timestamp, sign) 元组
    """
    timestamp = str(int(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
    return timestamp, sign


# ---------------------------------------------------------------------------
# 1.2 / 1.3 DingTalkClient
# ---------------------------------------------------------------------------

class DingTalkError(Exception):
    """钉钉 API 返回错误."""

    def __init__(self, errcode: int, errmsg: str) -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"DingTalk API error {errcode}: {errmsg}")


class DingTalkClient:
    """钉钉自定义机器人 Webhook 客户端."""

    def __init__(
        self,
        webhook_url: str,
        secret: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        self._webhook_url = webhook_url
        self._secret = secret
        self._timeout = timeout
        self._limiter = TokenBucketLimiter(capacity=20, refill_rate=20.0)

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """发送消息到钉钉群聊.

        Args:
            message: 完整的消息体 (msgtype + 对应内容)

        Returns:
            钉钉 API 响应 JSON

        Raises:
            DingTalkError: 钉钉返回非零 errcode
            httpx.HTTPStatusError: HTTP 状态码异常（重试后仍失败）
            httpx.RequestError: 网络错误（重试后仍失败）
        """
        self._limiter.acquire()

        timestamp, sign = sign_dingtalk(self._secret)
        url = f"{self._webhook_url}&timestamp={timestamp}&sign={sign}"

        last_exc: Exception | None = None

        for attempt in range(3):  # 最多 3 次
            try:
                response = httpx.post(url, json=message, timeout=self._timeout)
                data = response.json()

                errcode = data.get("errcode", -1)
                if errcode != 0:
                    raise DingTalkError(errcode, data.get("errmsg", "unknown"))

                return data

            except httpx.HTTPStatusError as exc:
                # 4xx 不重试
                if exc.response.status_code < 500:
                    raise
                last_exc = exc
                logger.warning("钉钉请求 %dxx 错误，第 %d 次重试", exc.response.status_code, attempt + 1)

            except httpx.RequestError as exc:
                last_exc = exc
                logger.warning("钉钉网络错误，第 %d 次重试: %s", attempt + 1, exc)

            except DingTalkError:
                # 业务错误不重试（errcode != 0）
                raise

            # 指数退避: 1s, 2s, 4s
            if attempt < 2:
                wait = 2 ** attempt  # 1, 2
                time.sleep(wait)

        # 3 次重试都失败
        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 1.5 令牌桶限流器
# ---------------------------------------------------------------------------

class TokenBucketLimiter:
    """令牌桶限流器（20 令牌/分钟）."""

    def __init__(self, capacity: int = 20, refill_rate: float = 20.0) -> None:
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = refill_rate  # tokens per 60 seconds
        self._last_refill = time.monotonic()

    def acquire(self) -> None:
        """获取一个令牌，无可用令牌时等待."""
        while True:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # 计算需要等待的时间
            deficit = 1.0 - self._tokens
            wait_time = deficit / (self._refill_rate / 60.0)
            time.sleep(wait_time)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        added = elapsed * (self._refill_rate / 60.0)
        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill = now
