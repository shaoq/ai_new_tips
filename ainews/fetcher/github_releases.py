"""GitHub Releases 采集器 — 监控指定仓库的版本发布和资源更新."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

RATE_LIMIT_THRESHOLD = 5
RATE_LIMIT_SLEEP = 1.5

# 默认监控仓库
DEFAULT_REPOS: list[str] = [
    # 工具类（关注版本发布）
    "anthropics/claude-code",
    "anthropics/anthropic-sdk-python",
    "anthropics/courses",
    # 资源/指南类（关注内容更新）
    "e2b-dev/awesome-ai-agents",
    "taishi-i/awesome-ChatGPT-repositories",
    "lukasmasuch/best-of-ml-python",
    "FlorianBruniaux/claude-code-ultimate-guide",
    # GitHub 仓库推荐类
    "GitHubDaily/GitHubDaily",
    "OpenGithubs/weekly",
    "OpenGithubs/github-weekly-rank",
    "GrowingGit/GitHub-Chinese-Top-Charts",
    "EvanLi/Github-Ranking",
]


class GitHubReleasesFetcher(BaseFetcher):
    """GitHub Releases 采集器.

    监控指定仓库的 releases，支持工具类、资源类和推荐类仓库。
    对无 release 的仓库记录 warning 并跳过。
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="github-releases", config=config)
        self._github_config = self._resolve_config(config)
        token = getattr(self._github_config, "token", "") or ""
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=headers,
        )

    def _resolve_config(self, config: Any) -> Any:
        """从配置对象提取 GitHubReleasesConfig."""
        if config is not None and hasattr(config, "repos"):
            return config
        try:
            from ainews.config.loader import get_config
            return get_config().sources.github_releases
        except Exception:
            return None

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """从所有监控仓库拉取 releases."""
        repos = self._get_repos()
        since_dt = self._parse_since(since)
        all_items: list[dict[str, Any]] = []

        for repo in repos:
            try:
                items = self._fetch_repo_releases(repo, since_dt)
                all_items.extend(items)
                logger.info(
                    "[github-releases] %s: 获取 %d 条 releases", repo, len(items),
                )
            except Exception:
                logger.warning(
                    "[github-releases] %s: 获取失败", repo, exc_info=True,
                )
            time.sleep(RATE_LIMIT_SLEEP)

        return all_items

    def _get_repos(self) -> list[str]:
        """获取监控仓库列表."""
        if self._github_config is not None:
            repos = getattr(self._github_config, "repos", [])
            if repos:
                return repos
        return DEFAULT_REPOS

    def _fetch_repo_releases(
        self,
        repo: str,
        since_dt: Optional[datetime],
    ) -> list[dict[str, Any]]:
        """拉取单个仓库的 releases."""
        url = f"{GITHUB_API_BASE}/repos/{repo}/releases"
        params: dict[str, str] = {"per_page": "10"}

        resp = self._client.get(url, params=params)
        self._check_rate_limit(resp)

        if resp.status_code == 404:
            logger.warning("[github-releases] %s: 仓库不存在或无 releases", repo)
            return []

        resp.raise_for_status()
        releases: list[dict[str, Any]] = resp.json()

        if not releases:
            logger.debug("[github-releases] %s: 无 releases", repo)
            return []

        items: list[dict[str, Any]] = []
        for release in releases:
            published_at = self._parse_release_time(release.get("published_at", ""))
            if since_dt and published_at and published_at <= since_dt:
                continue

            tag = release.get("tag_name", "")
            name = release.get("name", "") or tag
            title = f"[{repo}] {tag}: {name}" if name != tag else f"[{repo}] {tag}"
            body = release.get("body", "") or ""
            html_url = release.get("html_url", "")

            items.append({
                "url": html_url,
                "title": title,
                "content_raw": body,
                "source": "github-releases",
                "source_name": repo,
                "author": release.get("author", {}).get("login", ""),
                "published_at": published_at,
                "time": published_at.isoformat() if published_at else "",
                "metrics": {
                    "platform_score": 0,
                },
            })

        return items

    # ------------------------------------------------------------------
    # Rate limit
    # ------------------------------------------------------------------

    def _check_rate_limit(self, resp: httpx.Response) -> None:
        """检查 GitHub API 速率限制."""
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            remaining = int(remaining)
            if remaining <= RATE_LIMIT_THRESHOLD:
                reset_ts = resp.headers.get("X-RateLimit-Reset", "0")
                reset_time = int(reset_ts) - int(time.time())
                logger.warning(
                    "[github-releases] 速率限制即将耗尽 (remaining=%d), 等待 %ds",
                    remaining, max(reset_time, 0),
                )

    # ------------------------------------------------------------------
    # 时间解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_release_time(date_str: str) -> Optional[datetime]:
        """解析 GitHub release 的 ISO 8601 时间."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_since(since: Optional[str]) -> Optional[datetime]:
        """解析 since 水印为 datetime."""
        if not since:
            return None
        try:
            dt = datetime.fromisoformat(since)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最新 release 的 published_at 作为水印."""
        if not items:
            return None
        dates: list[datetime] = []
        for item in items:
            pub = item.get("published_at")
            if isinstance(pub, datetime):
                dates.append(pub)
        if dates:
            return max(dates).isoformat()
        return None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试 GitHub API 连通性."""
        try:
            start = time.monotonic()
            resp = self._client.get(f"{GITHUB_API_BASE}/zen")
            latency = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "detail": "GitHub API 连通正常",
                }
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
