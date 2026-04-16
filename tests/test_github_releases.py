"""测试 GitHub Releases 采集器 — API 集成、增量过滤、速率限制、连通性."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.fetcher.github_releases import (
    DEFAULT_REPOS,
    GitHubReleasesFetcher,
    RATE_LIMIT_THRESHOLD,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_release(
    tag_name: str = "v1.0.0",
    name: str = "",
    body: str = "Release notes",
    html_url: str = "https://github.com/test/repo/releases/tag/v1.0.0",
    published_at: str = "2026-04-15T12:00:00Z",
    author_login: str = "developer",
) -> dict[str, Any]:
    """构造单个 GitHub release JSON 对象."""
    return {
        "tag_name": tag_name,
        "name": name,
        "body": body,
        "html_url": html_url,
        "published_at": published_at,
        "author": {"login": author_login},
    }


@pytest.fixture
def fetcher() -> GitHubReleasesFetcher:
    """创建使用空配置的 GitHubReleasesFetcher（避免加载真实配置）."""
    cfg = MagicMock()
    cfg.repos = ["test/repo"]
    f = GitHubReleasesFetcher(config=cfg)
    return f


# ------------------------------------------------------------------
# 测试 fetch_items — 正常采集
# ------------------------------------------------------------------


class TestFetchItems:
    def test_fetch_releases_from_repo(self, fetcher: GitHubReleasesFetcher) -> None:
        """从有 releases 的仓库正常采集."""
        releases = [
            _make_release(
                tag_name="v2.0.0",
                name="Big Release",
                body="Major update with new features",
                html_url="https://github.com/test/repo/releases/tag/v2.0.0",
                published_at="2026-04-15T10:00:00Z",
                author_login="dev1",
            ),
            _make_release(
                tag_name="v1.1.0",
                name="Patch",
                body="Bug fixes",
                html_url="https://github.com/test/repo/releases/tag/v1.1.0",
                published_at="2026-04-10T08:00:00Z",
                author_login="dev2",
            ),
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = releases
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        with patch("ainews.fetcher.github_releases.time.sleep"):
            items = fetcher.fetch_items(since=None)

        assert len(items) == 2

    def test_fetch_repo_with_no_releases_404(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """仓库不存在或无 releases 返回 404 时返回空列表."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        with patch("ainews.fetcher.github_releases.time.sleep"):
            items = fetcher._fetch_repo_releases("nonexistent/repo", None)

        assert items == []

    def test_fetch_repo_with_empty_releases(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """仓库有 releases 端点但返回空列表."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        items = fetcher._fetch_repo_releases("test/repo", None)
        assert items == []

    def test_fetch_multiple_repos(self) -> None:
        """多仓库采集汇总."""
        cfg = MagicMock()
        cfg.repos = ["repo1/one", "repo2/two"]
        f = GitHubReleasesFetcher(config=cfg)

        release_1 = [_make_release(tag_name="v1.0.0", html_url="https://github.com/repo1/one/releases/tag/v1.0.0")]
        release_2 = [_make_release(tag_name="v2.0.0", html_url="https://github.com/repo2/two/releases/tag/v2.0.0")]

        resp_1 = MagicMock()
        resp_1.status_code = 200
        resp_1.json.return_value = release_1
        resp_1.headers = {"X-RateLimit-Remaining": "50"}
        resp_1.raise_for_status = MagicMock()

        resp_2 = MagicMock()
        resp_2.status_code = 200
        resp_2.json.return_value = release_2
        resp_2.headers = {"X-RateLimit-Remaining": "50"}
        resp_2.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.side_effect = [resp_1, resp_2]
        f._client = mock_client

        with patch("ainews.fetcher.github_releases.time.sleep"):
            items = f.fetch_items(since=None)

        assert len(items) == 2

    def test_single_repo_failure_doesnt_stop_others(self) -> None:
        """单个仓库失败不影响其他仓库."""
        cfg = MagicMock()
        cfg.repos = ["bad/repo", "good/repo"]
        f = GitHubReleasesFetcher(config=cfg)

        bad_resp = MagicMock()
        bad_resp.status_code = 500
        bad_resp.raise_for_status.side_effect = Exception("Server error")

        good_release = [_make_release(tag_name="v1.0.0", html_url="https://github.com/good/repo/releases/tag/v1.0.0")]
        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.json.return_value = good_release
        good_resp.headers = {"X-RateLimit-Remaining": "50"}
        good_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.side_effect = [bad_resp, good_resp]
        f._client = mock_client

        with patch("ainews.fetcher.github_releases.time.sleep"):
            items = f.fetch_items(since=None)

        assert len(items) == 1
        assert "good/repo" in items[0]["title"]


# ------------------------------------------------------------------
# 测试增量过滤 (since watermark)
# ------------------------------------------------------------------


class TestIncrementalFilter:
    def test_since_filters_old_releases(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """since 水印过滤旧的 releases."""
        releases = [
            _make_release(
                tag_name="v1.0.0",
                published_at="2026-04-10T10:00:00Z",
            ),
            _make_release(
                tag_name="v2.0.0",
                published_at="2026-04-16T10:00:00Z",
            ),
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = releases
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        # since = 2026-04-15, 应该过滤掉 v1.0.0
        since_dt = datetime(2026, 4, 15, 0, 0, 0, tzinfo=timezone.utc)
        items = fetcher._fetch_repo_releases("test/repo", since_dt)

        assert len(items) == 1
        assert items[0]["url"] == releases[1]["html_url"]

    def test_since_filters_all_releases(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """所有 releases 都旧于 since 水印时返回空列表."""
        releases = [
            _make_release(
                tag_name="v1.0.0",
                published_at="2026-04-01T10:00:00Z",
            ),
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = releases
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        since_dt = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        items = fetcher._fetch_repo_releases("test/repo", since_dt)
        assert items == []

    def test_since_none_returns_all(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """since=None 时返回所有 releases."""
        releases = [
            _make_release(tag_name="v1.0.0", published_at="2026-04-01T10:00:00Z"),
            _make_release(tag_name="v2.0.0", published_at="2026-04-15T10:00:00Z"),
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = releases
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        items = fetcher._fetch_repo_releases("test/repo", None)
        assert len(items) == 2


# ------------------------------------------------------------------
# 测试 release 字段映射
# ------------------------------------------------------------------


class TestReleaseFields:
    def test_all_fields_populated_correctly(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """release 对象各字段正确映射到 item 字典."""
        release = _make_release(
            tag_name="v3.0.0",
            name="Major Update",
            body="Breaking changes and new features",
            html_url="https://github.com/test/repo/releases/tag/v3.0.0",
            published_at="2026-04-15T12:30:00Z",
            author_login="alice",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [release]
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        items = fetcher._fetch_repo_releases("test/repo", None)

        assert len(items) == 1
        item = items[0]

        # title: "[repo] tag: name" 格式
        assert "[test/repo] v3.0.0: Major Update" == item["title"]
        assert item["content_raw"] == "Breaking changes and new features"
        assert item["url"] == "https://github.com/test/repo/releases/tag/v3.0.0"
        assert item["source"] == "github-releases"
        assert item["source_name"] == "test/repo"
        assert item["author"] == "alice"
        assert item["published_at"] is not None
        assert item["published_at"].year == 2026
        assert item["published_at"].month == 4
        assert item["published_at"].day == 15
        assert item["metrics"]["platform_score"] == 0

    def test_title_without_name_uses_tag(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """release 无 name 时标题只显示 tag."""
        release = _make_release(tag_name="v1.0.0", name="")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [release]
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        items = fetcher._fetch_repo_releases("test/repo", None)

        assert len(items) == 1
        # name == tag 时，标题只有 [repo] tag
        assert items[0]["title"] == "[test/repo] v1.0.0"

    def test_missing_body_defaults_to_empty(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """release 无 body 时 content_raw 为空字符串."""
        release = _make_release(body="")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [release]
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        items = fetcher._fetch_repo_releases("test/repo", None)
        assert items[0]["content_raw"] == ""

    def test_missing_author_defaults_to_empty(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """release 无 author 时 author 为空字符串."""
        release = _make_release()
        del release["author"]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [release]
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        items = fetcher._fetch_repo_releases("test/repo", None)
        assert items[0]["author"] == ""


# ------------------------------------------------------------------
# 测试速率限制检测
# ------------------------------------------------------------------


class TestRateLimit:
    def test_rate_limit_warning_logged(self, fetcher: GitHubReleasesFetcher) -> None:
        """速率限制即将耗尽时记录警告."""
        mock_resp = MagicMock()
        mock_resp.headers = {
            "X-RateLimit-Remaining": "3",
            "X-RateLimit-Reset": "1713199200",
        }

        with patch("ainews.fetcher.github_releases.logger") as mock_logger:
            fetcher._check_rate_limit(mock_resp)
            mock_logger.warning.assert_called_once()

    def test_rate_limit_ok_when_remaining_high(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """速率限制充足时不记录警告."""
        mock_resp = MagicMock()
        mock_resp.headers = {"X-RateLimit-Remaining": "50"}

        with patch("ainews.fetcher.github_releases.logger") as mock_logger:
            fetcher._check_rate_limit(mock_resp)
            mock_logger.warning.assert_not_called()

    def test_rate_limit_no_header(self, fetcher: GitHubReleasesFetcher) -> None:
        """响应无速率限制头时不报错."""
        mock_resp = MagicMock()
        mock_resp.headers = {}

        # Should not raise
        fetcher._check_rate_limit(mock_resp)


# ------------------------------------------------------------------
# 测试时间解析
# ------------------------------------------------------------------


class TestTimeParsing:
    def test_parse_release_time_iso(self) -> None:
        """解析标准 ISO 8601 时间."""
        dt = GitHubReleasesFetcher._parse_release_time("2026-04-15T12:30:00Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 15

    def test_parse_release_time_with_offset(self) -> None:
        """解析带时区偏移的 ISO 时间."""
        dt = GitHubReleasesFetcher._parse_release_time("2026-04-15T12:30:00+08:00")
        assert dt is not None
        assert dt.hour == 12

    def test_parse_release_time_empty(self) -> None:
        """空字符串返回 None."""
        assert GitHubReleasesFetcher._parse_release_time("") is None

    def test_parse_release_time_invalid(self) -> None:
        """无效时间返回 None."""
        assert GitHubReleasesFetcher._parse_release_time("not-a-date") is None

    def test_parse_since_iso(self) -> None:
        """解析 since 水印."""
        dt = GitHubReleasesFetcher._parse_since("2026-04-15T00:00:00+00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_parse_since_none(self) -> None:
        """since=None 返回 None."""
        assert GitHubReleasesFetcher._parse_since(None) is None

    def test_parse_since_invalid(self) -> None:
        """无效 since 字符串返回 None."""
        assert GitHubReleasesFetcher._parse_since("invalid") is None

    def test_parse_since_naive_gets_utc(self) -> None:
        """无时区的 since 字符串自动加 UTC."""
        dt = GitHubReleasesFetcher._parse_since("2026-04-15T00:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc


# ------------------------------------------------------------------
# 测试水印构建
# ------------------------------------------------------------------


class TestBuildCursor:
    def test_build_cursor_returns_latest(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """水印返回最新 release 的 published_at."""
        items = [
            {"url": "https://a.com", "published_at": datetime(2026, 4, 10, tzinfo=timezone.utc)},
            {"url": "https://b.com", "published_at": datetime(2026, 4, 14, tzinfo=timezone.utc)},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor is not None
        assert "2026-04-14" in cursor

    def test_build_cursor_empty(self, fetcher: GitHubReleasesFetcher) -> None:
        """空列表返回 None."""
        assert fetcher._build_cursor([]) is None

    def test_build_cursor_no_datetime(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """items 没有 published_at datetime 时返回 None."""
        items = [{"url": "https://a.com", "published_at": "2026-04-14"}]
        assert fetcher._build_cursor(items) is None


# ------------------------------------------------------------------
# 测试连通性
# ------------------------------------------------------------------


class TestConnection:
    def test_connection_ok(self, fetcher: GitHubReleasesFetcher) -> None:
        """GitHub API 连通正常."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Design is not just what it looks like."

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        with patch("ainews.fetcher.github_releases.time.monotonic", return_value=0):
            result = fetcher.test_connection()

        assert result["ok"] is True
        assert "latency_ms" in result

    def test_connection_non_200(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """GitHub API 返回非 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        fetcher._client = mock_client

        with patch("ainews.fetcher.github_releases.time.monotonic", return_value=0):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "403" in result["error"]

    def test_connection_network_error(
        self, fetcher: GitHubReleasesFetcher,
    ) -> None:
        """网络错误."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Network timeout")
        fetcher._client = mock_client

        with patch("ainews.fetcher.github_releases.time.monotonic", return_value=0):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "Network timeout" in result["error"]


# ------------------------------------------------------------------
# 测试 _get_repos
# ------------------------------------------------------------------


class TestGetRepos:
    def test_config_has_repos(self) -> None:
        """配置有 repos 时使用配置."""
        cfg = MagicMock()
        cfg.repos = ["custom/repo"]
        f = GitHubReleasesFetcher(config=cfg)
        assert f._get_repos() == ["custom/repo"]

    def test_config_empty_repos_uses_defaults(self) -> None:
        """配置 repos 为空列表时使用默认值."""
        cfg = MagicMock()
        cfg.repos = []
        f = GitHubReleasesFetcher(config=cfg)
        assert f._get_repos() == DEFAULT_REPOS

    def test_no_config_uses_defaults(self) -> None:
        """无配置时使用默认仓库列表."""
        f = GitHubReleasesFetcher(config=None)
        f._github_config = None
        assert f._get_repos() == DEFAULT_REPOS
