"""Obsidian Local REST API 客户端."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# API 版本前缀
API_PREFIX = "/v0"

# 重试配置
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]


class ObsidianClient:
    """Obsidian Local REST API 客户端，封装连接、认证、重试和降级逻辑."""

    def __init__(
        self,
        api_key: str,
        port: int = 27124,
        vault_path: str = "",
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._port = port
        self._vault_path = Path(vault_path) if vault_path else Path("")
        self._base_url = f"https://127.0.0.1:{port}{API_PREFIX}"
        self._timeout = timeout
        self._degraded = False

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "text/markdown",
            },
            verify=False,
            timeout=httpx.Timeout(timeout),
        )

    @property
    def degraded(self) -> bool:
        """是否处于文件系统降级模式."""
        return self._degraded

    @property
    def vault_path(self) -> Path:
        """Vault 文件系统路径."""
        return self._vault_path

    def health_check(self) -> bool:
        """检查 Obsidian REST API 是否可用.

        调用 GET / 验证连接，失败时切换为降级模式.
        """
        try:
            response = self._request("GET", "/")
            if response.status_code < 500:
                logger.info("Obsidian REST API 连接成功 (port=%s)", self._port)
                return True
            logger.warning(
                "Obsidian REST API 返回 %s，将降级为文件系统模式",
                response.status_code,
            )
            self._degraded = True
            return False
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "Obsidian REST API 连接失败: %s，将降级为文件系统模式",
                exc,
            )
            self._degraded = True
            return False

    # ---- REST API 操作 ----

    def put_vault_file(self, path: str, content: str) -> bool:
        """创建或覆盖 Vault 文件.

        Args:
            path: 相对于 Vault 根目录的路径，如 "AI-News/Industry/test.md"
            content: Markdown 内容
        """
        if self._degraded:
            return self._fs_write_file(path, content)

        try:
            response = self._request("PUT", f"/vault/{path}", content=content)
            if response.status_code in (200, 201, 204):
                logger.debug("REST API 写入成功: %s", path)
                return True
            logger.error("REST API 写入失败 %s: %s", path, response.status_code)
            return False
        except (httpx.ConnectError, httpx.TimeoutException):
            self._degraded = True
            return self._fs_write_file(path, content)

    def get_vault_file(self, path: str) -> str | None:
        """读取 Vault 文件内容."""
        if self._degraded:
            return self._fs_read_file(path)

        try:
            response = self._request("GET", f"/vault/{path}")
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            logger.error("REST API 读取失败 %s: %s", path, response.status_code)
            return None
        except (httpx.ConnectError, httpx.TimeoutException):
            self._degraded = True
            return self._fs_read_file(path)

    def patch_periodic_daily(self, heading: str, content: str) -> bool:
        """追加内容到当日 daily note 的指定 heading.

        REST API 模式: PATCH /periodic/daily/ + headers
        降级模式: 直接追加到文件系统
        """
        if self._degraded:
            # 降级模式需要调用方自行处理文件创建/追加
            return False

        try:
            response = self._request(
                "PATCH",
                "/periodic/daily/",
                content=content,
                extra_headers={
                    "Target-Type": "heading",
                    "Operation": "append",
                },
            )
            if response.status_code in (200, 204):
                logger.debug("REST API 每日笔记追加成功")
                return True
            logger.error(
                "REST API 每日笔记追加失败: %s", response.status_code
            )
            return False
        except (httpx.ConnectError, httpx.TimeoutException):
            self._degraded = True
            return False

    def patch_frontmatter(self, path: str, fields: dict[str, Any]) -> bool:
        """更新 Vault 文件的 frontmatter 字段.

        REST API 模式: PATCH /vault/{path} + Target-Type: frontmatter
        降级模式: 不支持精确 frontmatter 更新
        """
        if self._degraded:
            logger.debug("降级模式不支持 frontmatter 更新: %s", path)
            return False

        try:
            import json

            response = self._request(
                "PATCH",
                f"/vault/{path}",
                content=json.dumps(fields),
                extra_headers={
                    "Content-Type": "application/json",
                    "Target-Type": "frontmatter",
                },
            )
            if response.status_code in (200, 204):
                logger.debug("REST API frontmatter 更新成功: %s", path)
                return True
            logger.error(
                "REST API frontmatter 更新失败 %s: %s",
                path,
                response.status_code,
            )
            return False
        except (httpx.ConnectError, httpx.TimeoutException):
            self._degraded = True
            return False

    def search_simple(self, query: str) -> list[dict[str, Any]]:
        """搜索 Vault 内容.

        Returns:
            匹配结果列表，每个结果包含 path、filename、score 等字段
        """
        if self._degraded:
            return self._fs_search(query)

        try:
            import json

            response = self._request(
                "POST",
                "/search/simple/",
                content=json.dumps({"query": query}),
                extra_headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            return []
        except (httpx.ConnectError, httpx.TimeoutException):
            self._degraded = True
            return self._fs_search(query)

    # ---- 带重试的请求 ----

    def _request(
        self,
        method: str,
        url: str,
        content: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """发送 HTTP 请求，带重试和指数退避."""
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                headers: dict[str, str] = {}
                if extra_headers:
                    headers.update(extra_headers)

                response = self._client.request(
                    method,
                    url,
                    content=content.encode("utf-8") if content else None,
                    headers=headers if headers else None,
                )

                # 4xx 不重试
                if 400 <= response.status_code < 500:
                    return response

                # 5xx 重试
                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(
                            "请求 %s %s 返回 %s，%ds 后重试 (%d/%d)",
                            method,
                            url,
                            response.status_code,
                            delay,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        time.sleep(delay)
                        continue
                    return response

                return response

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        "请求 %s %s 连接失败: %s，%ds 后重试 (%d/%d)",
                        method,
                        url,
                        exc,
                        delay,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "请求 %s %s 重试耗尽: %s", method, url, exc
                    )

        assert last_exc is not None
        raise last_exc

    # ---- 文件系统降级操作 ----

    def _fs_write_file(self, path: str, content: str) -> bool:
        """文件系统降级: 写入文件."""
        full_path = self._vault_path / path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            logger.debug("文件系统写入成功: %s", full_path)
            return True
        except OSError as exc:
            logger.error("文件系统写入失败 %s: %s", full_path, exc)
            return False

    def _fs_read_file(self, path: str) -> str | None:
        """文件系统降级: 读取文件."""
        full_path = self._vault_path / path
        try:
            if full_path.exists():
                return full_path.read_text(encoding="utf-8")
            return None
        except OSError as exc:
            logger.error("文件系统读取失败 %s: %s", full_path, exc)
            return None

    def _fs_append_file(self, path: str, content: str) -> bool:
        """文件系统降级: 追加内容到文件."""
        full_path = self._vault_path / path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "a", encoding="utf-8") as f:
                f.write(content)
            logger.debug("文件系统追加成功: %s", full_path)
            return True
        except OSError as exc:
            logger.error("文件系统追加失败 %s: %s", full_path, exc)
            return False

    def _fs_search(self, query: str) -> list[dict[str, Any]]:
        """文件系统降级: 简单搜索（按文件名匹配）."""
        results: list[dict[str, Any]] = []
        if not self._vault_path.exists():
            return results
        for md_file in self._vault_path.rglob("*.md"):
            if query.lower() in md_file.stem.lower():
                rel = md_file.relative_to(self._vault_path)
                results.append({
                    "path": str(rel),
                    "filename": md_file.stem,
                })
        return results

    def close(self) -> None:
        """关闭 HTTP 客户端."""
        self._client.close()

    def __enter__(self) -> ObsidianClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
