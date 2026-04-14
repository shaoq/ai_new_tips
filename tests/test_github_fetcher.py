"""测试 GitHub Trending 采集器 — Search API 查询构建、normalize、速率限制."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.config.settings import GitHubConfig
from ainews.fetcher.github import GITHUB_SEARCH_API, RATE_LIMIT_THRESHOLD, GitHubFetcher


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def github_config() -> GitHubConfig:
    return GitHubConfig(
        token="ghp_test_token",
        topics=["machine-learning", "llm", "ai", "transformer"],
        languages=["python", "typescript"],
        min_stars=50,
    )


@pytest.fixture
def fetcher(github_config: GitHubConfig) -> GitHubFetcher:
    """创建 GitHubFetcher 并替换 httpx.Client 为 mock."""
    with patch("ainews.fetcher.github.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        f = GitHubFetcher(config=github_config)
        # 保存 mock_client 引用以便测试中使用
        f._mock_client = mock_client
    return f


# ------------------------------------------------------------------
# 测试 _build_query
# ------------------------------------------------------------------


class TestBuildQuery:
    def test_default_query_with_topics(self, fetcher: GitHubFetcher) -> None:
        """默认查询包含 topic 过滤."""
        query = fetcher._build_query()
        assert "topic:machine-learning" in query
        assert "topic:llm" in query
        assert "topic:ai" in query
        assert "topic:transformer" in query

    def test_language_filter(self, fetcher: GitHubFetcher) -> None:
        """查询包含 language 过滤."""
        query = fetcher._build_query()
        assert "language:python" in query
        assert "language:typescript" in query

    def test_min_stars_filter(self, fetcher: GitHubFetcher) -> None:
        """查询包含 stars 最低要求."""
        query = fetcher._build_query()
        assert "stars:>=50" in query

    def test_since_parameter(self, fetcher: GitHubFetcher) -> None:
        """传入 since 时使用精确日期窗口."""
        query = fetcher._build_query(since="2026-04-01")
        assert "created:>2026-04-01" in query

    def test_default_since_is_last_week(self, fetcher: GitHubFetcher) -> None:
        """不传 since 时默认拉取最近 7 天."""
        query = fetcher._build_query()
        week_ago = (
            datetime.now(tz=timezone.utc) - timedelta(days=7)
        ).strftime("%Y-%m-%d")
        assert f"created:>{week_ago}" in query

    def test_no_topics(self, fetcher: GitHubFetcher) -> None:
        """topics 为空时不包含 topic 过滤."""
        fetcher._github_config.topics = []
        query = fetcher._build_query()
        assert "topic:" not in query

    def test_no_languages(self, fetcher: GitHubFetcher) -> None:
        """languages 为空时不包含 language 过滤."""
        fetcher._github_config.languages = []
        query = fetcher._build_query()
        assert "language:" not in query


# ------------------------------------------------------------------
# 测试 _normalize
# ------------------------------------------------------------------


class TestNormalize:
    def test_basic_repo(self, fetcher: GitHubFetcher) -> None:
        """标准化基本仓库数据."""
        repo = {
            "html_url": "https://github.com/user/awesome-llm",
            "full_name": "user/awesome-llm",
            "description": "A curated list of LLM resources",
            "created_at": "2026-04-10T12:00:00Z",
            "stargazers_count": 1500,
            "owner": {"login": "user"},
        }
        result = fetcher._normalize(repo)

        assert result is not None
        assert result["url"] == "https://github.com/user/awesome-llm"
        assert "awesome-llm" in result["title"]
        assert "curated list of LLM resources" in result["title"]
        assert result["source"] == "github"
        assert result["source_name"] == "GitHub Trending"
        assert result["author"] == "user"
        assert result["metrics"]["platform_score"] == 1500.0
        assert result["metrics"]["upvote_count"] == 1500

    def test_repo_without_url(self, fetcher: GitHubFetcher) -> None:
        """缺少 html_url 返回 None."""
        repo = {
            "full_name": "user/test",
            "description": "No URL",
        }
        result = fetcher._normalize(repo)
        assert result is None

    def test_empty_url(self, fetcher: GitHubFetcher) -> None:
        """空 html_url 返回 None."""
        repo = {
            "html_url": "",
            "full_name": "user/test",
        }
        result = fetcher._normalize(repo)
        assert result is None

    def test_repo_without_description(self, fetcher: GitHubFetcher) -> None:
        """缺少 description 时使用空字符串."""
        repo = {
            "html_url": "https://github.com/user/minimal",
            "full_name": "user/minimal",
            "description": None,
            "created_at": "2026-04-10T12:00:00Z",
            "stargazers_count": 100,
            "owner": {"login": "user"},
        }
        result = fetcher._normalize(repo)

        assert result is not None
        assert result["content_raw"] == ""

    def test_repo_without_owner(self, fetcher: GitHubFetcher) -> None:
        """缺少 owner 时 author 为空字符串."""
        repo = {
            "html_url": "https://github.com/user/repo",
            "full_name": "user/repo",
            "description": "Some repo",
            "stargazers_count": 50,
        }
        result = fetcher._normalize(repo)

        assert result is not None
        assert result["author"] == ""

    def test_published_at_parsed(self, fetcher: GitHubFetcher) -> None:
        """正确解析 created_at 为 datetime."""
        repo = {
            "html_url": "https://github.com/user/repo",
            "full_name": "user/repo",
            "description": "Test",
            "created_at": "2026-04-10T12:00:00Z",
            "stargazers_count": 50,
        }
        result = fetcher._normalize(repo)

        assert result is not None
        assert isinstance(result["published_at"], datetime)
        assert result["published_at"].year == 2026
        assert result["published_at"].month == 4
        assert result["published_at"].day == 10

    def test_invalid_created_at(self, fetcher: GitHubFetcher) -> None:
        """无效 created_at 时 published_at 为 None."""
        repo = {
            "html_url": "https://github.com/user/repo",
            "full_name": "user/repo",
            "description": "Test",
            "created_at": "not-a-date",
            "stargazers_count": 50,
        }
        result = fetcher._normalize(repo)

        assert result is not None
        assert result["published_at"] is None
        assert result["time"] == ""

    def test_zero_stars(self, fetcher: GitHubFetcher) -> None:
        """stargazers_count 为 0 时正常处理."""
        repo = {
            "html_url": "https://github.com/user/new-repo",
            "full_name": "user/new-repo",
            "description": "Brand new",
            "stargazers_count": 0,
            "owner": {"login": "user"},
        }
        result = fetcher._normalize(repo)

        assert result is not None
        assert result["metrics"]["platform_score"] == 0.0


# ------------------------------------------------------------------
# 测试 fetch_items (mocked httpx)
# ------------------------------------------------------------------


class TestFetchItems:
    def _make_github_response(
        self,
        repos: list[dict[str, Any]],
        status_code: int = 200,
        remaining: str = "50",
    ) -> MagicMock:
        """构造 GitHub Search API mock 响应."""
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"X-RateLimit-Remaining": remaining}
        resp.json.return_value = {
            "total_count": len(repos),
            "items": repos,
        }
        resp.raise_for_status = MagicMock()
        return resp

    def test_basic_fetch(self, fetcher: GitHubFetcher) -> None:
        """基本采集流程 — 返回标准化条目."""
        repos = [
            {
                "html_url": "https://github.com/user/llm-tool",
                "full_name": "user/llm-tool",
                "description": "LLM tooling",
                "created_at": "2026-04-12T10:00:00Z",
                "stargazers_count": 200,
                "owner": {"login": "user"},
            },
            {
                "html_url": "https://github.com/org/ai-framework",
                "full_name": "org/ai-framework",
                "description": "AI framework",
                "created_at": "2026-04-13T08:00:00Z",
                "stargazers_count": 500,
                "owner": {"login": "org"},
            },
        ]

        mock_resp = self._make_github_response(repos)
        fetcher._client = MagicMock()
        fetcher._client.get.return_value = mock_resp

        items = fetcher.fetch_items()

        assert len(items) == 2
        assert items[0]["url"] == "https://github.com/user/llm-tool"
        assert items[1]["url"] == "https://github.com/org/ai-framework"

    def test_fetch_with_since_cursor(self, fetcher: GitHubFetcher) -> None:
        """传入 since 时传递日期部分到 _build_query."""
        repos = [
            {
                "html_url": "https://github.com/user/new-repo",
                "full_name": "user/new-repo",
                "description": "New",
                "created_at": "2026-04-13T00:00:00Z",
                "stargazers_count": 100,
                "owner": {"login": "user"},
            },
        ]

        mock_resp = self._make_github_response(repos)
        fetcher._client = MagicMock()
        fetcher._client.get.return_value = mock_resp

        items = fetcher.fetch_items(since="2026-04-10T00:00:00+00:00")

        assert len(items) == 1
        # 验证传递给 API 的查询包含 since 日期
        call_args = fetcher._client.get.call_args
        query_param = call_args[1]["params"]["q"]
        assert "created:>2026-04-10" in query_param

    def test_empty_results(self, fetcher: GitHubFetcher) -> None:
        """GitHub 返回空结果."""
        mock_resp = self._make_github_response([])
        fetcher._client = MagicMock()
        fetcher._client.get.return_value = mock_resp

        items = fetcher.fetch_items()
        assert len(items) == 0

    def test_skip_repo_without_url(self, fetcher: GitHubFetcher) -> None:
        """跳过没有 html_url 的仓库."""
        repos = [
            {
                "full_name": "user/no-url",
                "description": "Missing URL",
                "stargazers_count": 100,
            },
        ]

        mock_resp = self._make_github_response(repos)
        fetcher._client = MagicMock()
        fetcher._client.get.return_value = mock_resp

        items = fetcher.fetch_items()
        assert len(items) == 0

    def test_backfill_triggers_weekly_fetch(self, fetcher: GitHubFetcher) -> None:
        """backfill_days > 7 触发按周分批拉取."""
        repos = [
            {
                "html_url": "https://github.com/user/old-repo",
                "full_name": "user/old-repo",
                "description": "Old",
                "created_at": "2026-03-01T00:00:00Z",
                "stargazers_count": 100,
                "owner": {"login": "user"},
            },
        ]

        mock_resp = self._make_github_response(repos)
        fetcher._client = MagicMock()
        fetcher._client.get.return_value = mock_resp

        with patch("ainews.fetcher.github.time.sleep"):
            items = fetcher.fetch_items(backfill_days=21)

        # 21 days => 3 weeks => 3 API calls
        assert fetcher._client.get.call_count == 3
        assert len(items) == 3  # same repo returned 3 times

    def test_invalid_since_ignored(self, fetcher: GitHubFetcher) -> None:
        """无效 since 值被忽略，回退到默认时间窗口."""
        repos = [
            {
                "html_url": "https://github.com/user/repo",
                "full_name": "user/repo",
                "description": "Test",
                "created_at": "2026-04-12T00:00:00Z",
                "stargazers_count": 100,
                "owner": {"login": "user"},
            },
        ]

        mock_resp = self._make_github_response(repos)
        fetcher._client = MagicMock()
        fetcher._client.get.return_value = mock_resp

        items = fetcher.fetch_items(since="not-a-valid-timestamp")

        assert len(items) == 1


# ------------------------------------------------------------------
# 测试 _build_cursor
# ------------------------------------------------------------------


class TestBuildCursor:
    def test_returns_max_timestamp(self, fetcher: GitHubFetcher) -> None:
        """返回最大的 time 值作为水印."""
        items = [
            {"url": "https://github.com/a", "time": "2026-04-10T12:00:00+00:00"},
            {"url": "https://github.com/b", "time": "2026-04-13T08:00:00+00:00"},
            {"url": "https://github.com/c", "time": "2026-04-11T10:00:00+00:00"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-13T08:00:00+00:00"

    def test_empty_items(self, fetcher: GitHubFetcher) -> None:
        """空列表返回 None."""
        cursor = fetcher._build_cursor([])
        assert cursor is None

    def test_items_without_time(self, fetcher: GitHubFetcher) -> None:
        """所有条目没有 time 字段返回 None."""
        items = [
            {"url": "https://github.com/a"},
            {"url": "https://github.com/b"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor is None

    def test_mixed_time_and_empty(self, fetcher: GitHubFetcher) -> None:
        """部分条目有 time 时只从有效条目中取最大值."""
        items = [
            {"url": "https://github.com/a", "time": "2026-04-10T12:00:00+00:00"},
            {"url": "https://github.com/b", "time": ""},
            {"url": "https://github.com/c", "time": "2026-04-12T10:00:00+00:00"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-12T10:00:00+00:00"


# ------------------------------------------------------------------
# 测试 _check_rate_limit
# ------------------------------------------------------------------


class TestCheckRateLimit:
    def test_no_warning_when_plenty_remaining(self, fetcher: GitHubFetcher) -> None:
        """剩余请求充足时不 sleep."""
        resp = MagicMock()
        resp.headers = {"X-RateLimit-Remaining": "50"}

        with patch("ainews.fetcher.github.time.sleep") as mock_sleep:
            fetcher._check_rate_limit(resp)
            mock_sleep.assert_not_called()

    def test_warning_when_low_remaining(self, fetcher: GitHubFetcher) -> None:
        """剩余请求低于阈值时发出警告."""
        resp = MagicMock()
        resp.headers = {
            "X-RateLimit-Remaining": "3",
            "X-RateLimit-Reset": str(int(time.time()) + 10),
        }

        with patch("ainews.fetcher.github.time.sleep") as mock_sleep:
            fetcher._check_rate_limit(resp)
            mock_sleep.assert_called_once()
            # 验证 sleep 时间合理（约 10s + 1s）
            sleep_arg = mock_sleep.call_args[0][0]
            assert 0 < sleep_arg <= 15

    def test_no_sleep_when_wait_too_long(self, fetcher: GitHubFetcher) -> None:
        """等待时间超过 300 秒时不 sleep."""
        resp = MagicMock()
        resp.headers = {
            "X-RateLimit-Remaining": "2",
            "X-RateLimit-Reset": str(int(time.time()) + 600),
        }

        with patch("ainews.fetcher.github.time.sleep") as mock_sleep:
            fetcher._check_rate_limit(resp)
            mock_sleep.assert_not_called()

    def test_no_rate_limit_headers(self, fetcher: GitHubFetcher) -> None:
        """无速率限制头时不报错."""
        resp = MagicMock()
        resp.headers = {}

        with patch("ainews.fetcher.github.time.sleep") as mock_sleep:
            fetcher._check_rate_limit(resp)
            mock_sleep.assert_not_called()

    def test_exactly_at_threshold(self, fetcher: GitHubFetcher) -> None:
        """剩余请求数恰好等于阈值时触发等待."""
        resp = MagicMock()
        resp.headers = {
            "X-RateLimit-Remaining": str(RATE_LIMIT_THRESHOLD),
            "X-RateLimit-Reset": str(int(time.time()) + 5),
        }

        with patch("ainews.fetcher.github.time.sleep") as mock_sleep:
            fetcher._check_rate_limit(resp)
            mock_sleep.assert_called_once()


# ------------------------------------------------------------------
# 测试 test_connection
# ------------------------------------------------------------------


class TestConnection:
    def test_connection_ok(self, fetcher: GitHubFetcher) -> None:
        """API 返回 200 表示连通正常."""
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"X-RateLimit-Remaining": "58"}
        resp.json.return_value = {"total_count": 12345}

        fetcher._client = MagicMock()
        fetcher._client.get.return_value = resp

        result = fetcher.test_connection()
        assert result["ok"] is True
        assert "latency_ms" in result
        assert "12345" in result["detail"]
        assert "58" in result["detail"]

    def test_connection_rate_limited(self, fetcher: GitHubFetcher) -> None:
        """API 返回 403 表示速率限制."""
        resp = MagicMock()
        resp.status_code = 403

        fetcher._client = MagicMock()
        fetcher._client.get.return_value = resp

        result = fetcher.test_connection()
        assert result["ok"] is False
        assert "PAT" in result["error"]

    def test_connection_server_error(self, fetcher: GitHubFetcher) -> None:
        """API 返回 500 表示服务不可用."""
        resp = MagicMock()
        resp.status_code = 500

        fetcher._client = MagicMock()
        fetcher._client.get.return_value = resp

        result = fetcher.test_connection()
        assert result["ok"] is False
        assert "500" in result["error"]

    def test_connection_network_error(self, fetcher: GitHubFetcher) -> None:
        """网络异常时返回错误."""
        fetcher._client = MagicMock()
        fetcher._client.get.side_effect = Exception("Connection refused")

        result = fetcher.test_connection()
        assert result["ok"] is False
        assert "Connection refused" in result["error"]
