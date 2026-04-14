"""GitHub Trending 采集器 — Search API，stars 速度热度信号."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from ainews.config.settings import GitHubConfig
from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
RATE_LIMIT_THRESHOLD = 5  # 剩余请求低于此值时警告


class GitHubFetcher(BaseFetcher):
    """GitHub Trending 采集器.

    通过 GitHub Search API 拉取 AI 相关新仓库，
    stars 数作为热度信号。支持 PAT 认证提升速率限制。
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="github", config=config)
        self._github_config = self._resolve_config(config)
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self._github_config.token:
            headers["Authorization"] = f"token {self._github_config.token}"
        self._client = httpx.Client(timeout=30.0, headers=headers)

    def _resolve_config(self, config: Any) -> GitHubConfig:
        """从配置对象提取 GitHubConfig."""
        if isinstance(config, GitHubConfig):
            return config
        try:
            from ainews.config.loader import get_config
            app_config = get_config()
            return app_config.sources.github
        except Exception:
            return GitHubConfig()

    def _build_query(self, since: Optional[str] = None) -> str:
        """构建 GitHub Search API 查询字符串."""
        cfg = self._github_config
        parts: list[str] = []

        # Topic 过滤
        if cfg.topics:
            topic_parts = [f"topic:{t}" for t in cfg.topics]
            parts.append(" ".join(topic_parts))

        # Language 过滤
        if cfg.languages:
            lang_parts = [f"language:{l}" for l in cfg.languages]
            parts.append(" ".join(lang_parts))

        # 时间窗口
        if since:
            parts.append(f"created:>{since}")
        else:
            # 默认拉取最近 7 天
            week_ago = (
                datetime.now(tz=timezone.utc) - timedelta(days=7)
            ).strftime("%Y-%m-%d")
            parts.append(f"created:>{week_ago}")

        # Stars 最低要求
        parts.append(f"stars:>={cfg.min_stars}")

        return " ".join(parts)

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """检查 GitHub API 速率限制."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            remaining = int(remaining)
            if remaining <= RATE_LIMIT_THRESHOLD:
                logger.warning(
                    "[github] 速率限制即将耗尽: 剩余 %d 次请求", remaining,
                )
                # 如果接近限制，等待 reset
                reset_at = response.headers.get("X-RateLimit-Reset")
                if reset_at:
                    wait_seconds = max(
                        0, int(reset_at) - int(time.time()) + 1,
                    )
                    if wait_seconds <= 300:  # 最多等 5 分钟
                        logger.info(
                            "[github] 等待速率重置: %ds", wait_seconds,
                        )
                        time.sleep(wait_seconds)

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """拉取 GitHub 上的 AI 相关新仓库."""
        # 如果有 cursor，从 cursor 之后开始拉取
        if since:
            try:
                # since 是 ISO 时间戳
                datetime.fromisoformat(since.replace("Z", "+00:00"))
                query_since = since[:10]  # 取日期部分
            except (ValueError, TypeError):
                query_since = None
        else:
            query_since = None

        if backfill_days and backfill_days > 7:
            # 回填模式：按周分批
            return self._fetch_backfill(backfill_days)

        query = self._build_query(since=query_since)
        return self._search(query)

    def _fetch_backfill(self, backfill_days: int) -> list[dict[str, Any]]:
        """回填模式：按周分批拉取."""
        all_items: list[dict[str, Any]] = []
        today = datetime.now(tz=timezone.utc)
        weeks = (backfill_days + 6) // 7

        for i in range(weeks):
            end = today - timedelta(weeks=i)
            start = end - timedelta(weeks=1)
            since_str = start.strftime("%Y-%m-%d")
            query = self._build_query()
            # 替换时间窗口
            query = query.replace(
                f"created:>{(today - timedelta(days=7)).strftime('%Y-%m-%d')}",
                f"created:{since_str}..{end.strftime('%Y-%m-%d')}",
            )
            items = self._search(query)
            all_items.extend(items)
            logger.info(
                "[github] 回填 %s~%s: %d 个仓库",
                since_str, end.strftime("%Y-%m-%d"), len(items),
            )
            time.sleep(2.0)

        return all_items

    def _search(self, query: str) -> list[dict[str, Any]]:
        """执行 GitHub Search API 查询."""
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
        }

        resp = self._client.get(GITHUB_SEARCH_API, params=params)
        self._check_rate_limit(resp)
        resp.raise_for_status()

        data = resp.json()
        repos = data.get("items", [])
        return [item for repo in repos if (item := self._normalize(repo)) is not None]

    # ------------------------------------------------------------------
    # normalize
    # ------------------------------------------------------------------

    def _normalize(self, repo: dict[str, Any]) -> Optional[dict[str, Any]]:
        """将 GitHub Repo 映射为统一 Article 字典."""
        html_url = repo.get("html_url", "")
        if not html_url:
            return None

        full_name = repo.get("full_name", "")
        description = repo.get("description", "") or ""

        published_at: Optional[datetime] = None
        created_at = repo.get("created_at", "")
        if created_at:
            try:
                published_at = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00"),
                )
            except (ValueError, TypeError):
                published_at = None

        return {
            "url": html_url,
            "title": f"{full_name}: {description}".strip(": "),
            "content_raw": description,
            "source": "github",
            "source_name": "GitHub Trending",
            "author": repo.get("owner", {}).get("login", ""),
            "published_at": published_at,
            "time": published_at.isoformat() if published_at else "",
            "metrics": {
                "platform_score": float(repo.get("stargazers_count", 0)),
                "upvote_count": repo.get("stargazers_count", 0),
            },
        }

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最大的 created_at 作为水印."""
        if not items:
            return None
        times = [item.get("time", "") for item in items if item.get("time")]
        return max(times) if times else None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试 GitHub API 连通性."""
        try:
            start = time.monotonic()
            resp = self._client.get(
                GITHUB_SEARCH_API,
                params={"q": "topic:ai", "per_page": 1},
                timeout=10,
            )
            latency = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("total_count", 0)
                remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "detail": f"GitHub API 可用，AI 相关仓库 {total} 个，剩余请求 {remaining}",
                }
            if resp.status_code == 403:
                return {"ok": False, "error": "速率限制已耗尽，请配置 GitHub PAT"}
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
