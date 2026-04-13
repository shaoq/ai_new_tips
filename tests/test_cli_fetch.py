"""测试 CLI fetch 和 sources 子命令."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ainews.cli.main import app


runner = CliRunner()


# ------------------------------------------------------------------
# 测试 fetch 命令
# ------------------------------------------------------------------

class TestFetchCommand:
    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_default(self, mock_run: MagicMock) -> None:
        """测试默认采集（全部源）."""
        from ainews.fetcher.runner import FetchResult, FetchSummary

        mock_run.return_value = FetchSummary(results=[
            FetchResult(source="hackernews", ok=True, articles=[], elapsed_ms=100),
            FetchResult(source="arxiv", ok=True, articles=[], elapsed_ms=200),
        ])

        result = runner.invoke(app, ["fetch", "run"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            sources=None, backfill_days=None, force=False, dry_run=False
        )

    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_with_source(self, mock_run: MagicMock) -> None:
        """测试指定源采集."""
        from ainews.fetcher.runner import FetchResult, FetchSummary

        mock_run.return_value = FetchSummary(results=[
            FetchResult(source="hackernews", ok=True, articles=[], elapsed_ms=100),
        ])

        result = runner.invoke(app, ["fetch", "run", "--source", "hackernews"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            sources=["hackernews"], backfill_days=None, force=False, dry_run=False
        )

    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_with_backfill(self, mock_run: MagicMock) -> None:
        """测试回填采集."""
        from ainews.fetcher.runner import FetchResult, FetchSummary

        mock_run.return_value = FetchSummary(results=[])

        result = runner.invoke(app, ["fetch", "run", "--backfill", "7"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            sources=None, backfill_days=7, force=False, dry_run=False
        )

    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_force(self, mock_run: MagicMock) -> None:
        """测试强制模式."""
        from ainews.fetcher.runner import FetchResult, FetchSummary

        mock_run.return_value = FetchSummary(results=[])

        result = runner.invoke(app, ["fetch", "run", "--force"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            sources=None, backfill_days=None, force=True, dry_run=False
        )

    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_dry_run(self, mock_run: MagicMock) -> None:
        """测试预览模式."""
        from ainews.fetcher.runner import FetchResult, FetchSummary

        mock_run.return_value = FetchSummary(results=[])

        result = runner.invoke(app, ["fetch", "run", "--dry-run"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            sources=None, backfill_days=None, force=False, dry_run=True
        )

    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_multiple_sources(self, mock_run: MagicMock) -> None:
        """测试多源采集."""
        from ainews.fetcher.runner import FetchResult, FetchSummary

        mock_run.return_value = FetchSummary(results=[])

        result = runner.invoke(app, ["fetch", "run", "--source", "hackernews,arxiv"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            sources=["hackernews", "arxiv"], backfill_days=None, force=False, dry_run=False
        )

    @patch("ainews.cli.fetch.run_fetch")
    def test_fetch_shows_results(self, mock_run: MagicMock) -> None:
        """测试结果展示."""
        from ainews.fetcher.runner import FetchResult, FetchSummary
        from ainews.storage.models import Article

        articles = [Article(url="https://a.com", title="Test")]
        mock_run.return_value = FetchSummary(results=[
            FetchResult(source="hackernews", ok=True, articles=articles, elapsed_ms=100),
            FetchResult(source="arxiv", ok=False, error="timeout", elapsed_ms=5000),
        ])

        result = runner.invoke(app, ["fetch", "run"])
        assert result.exit_code == 0
        assert "hackernews" in result.output
        assert "arxiv" in result.output


# ------------------------------------------------------------------
# 测试 sources 命令
# ------------------------------------------------------------------

class TestSourcesCommand:
    def test_sources_list(self) -> None:
        """测试列出数据源."""
        with patch("ainews.cli.sources.get_fetcher") as mock_get:
            mock_fetcher = MagicMock()
            mock_fetcher.test_connection.return_value = {"ok": True, "latency_ms": 50}
            mock_get.return_value = mock_fetcher

            result = runner.invoke(app, ["sources", "list"])
            assert result.exit_code == 0

    def test_sources_test(self) -> None:
        """测试连通性测试."""
        with patch("ainews.cli.sources.get_fetcher") as mock_get:
            mock_fetcher = MagicMock()
            mock_fetcher.test_connection.return_value = {
                "ok": True, "latency_ms": 120, "detail": "OK"
            }
            mock_get.return_value = mock_fetcher

            result = runner.invoke(app, ["sources", "test", "hackernews"])
            assert result.exit_code == 0
            assert "成功" in result.output

    def test_sources_test_unknown(self) -> None:
        """测试未知源."""
        result = runner.invoke(app, ["sources", "test", "unknown_source"])
        assert result.exit_code == 1

    def test_sources_add_rss_missing_args(self) -> None:
        """测试 RSS 添加缺少参数."""
        result = runner.invoke(app, ["sources", "add", "rss"])
        assert result.exit_code == 1

    def test_sources_remove(self) -> None:
        """测试移除源."""
        with patch("ainews.cli.sources._set_source_enabled"):
            result = runner.invoke(app, ["sources", "remove", "rss:openai-blog"])
            # 即使源不存在也不应崩溃
            assert result.exit_code == 0 or "不存在" in result.output

    def test_sources_enable(self) -> None:
        """测试启用源."""
        with patch("ainews.cli.sources._set_source_enabled") as mock_set:
            with patch("ainews.config.loader.get_config") as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.model_dump.return_value = {
                    "sources": {"hackernews": {"enabled": True, "keywords": []}},
                    "llm": {"base_url": "", "api_key": "", "model": "", "max_tokens": 1024},
                    "obsidian": {"vault_path": "", "api_key": "", "port": 27124},
                    "dingtalk": {"webhook_url": "", "secret": ""},
                    "logging": {"level": "INFO", "path": ""},
                }
                mock_config.return_value = mock_cfg
                result = runner.invoke(app, ["sources", "enable", "hackernews"])
                assert result.exit_code == 0

    def test_sources_disable(self) -> None:
        """测试禁用源."""
        with patch("ainews.config.loader.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.model_dump.return_value = {
                "sources": {"arxiv": {"enabled": True, "keywords": []}},
                "llm": {"base_url": "", "api_key": "", "model": "", "max_tokens": 1024},
                "obsidian": {"vault_path": "", "api_key": "", "port": 27124},
                "dingtalk": {"webhook_url": "", "secret": ""},
                "logging": {"level": "INFO", "path": ""},
            }
            mock_config.return_value = mock_cfg
            with patch("ainews.config.loader.save_config"):
                with patch("ainews.config.loader.clear_config_cache"):
                    result = runner.invoke(app, ["sources", "disable", "arxiv"])
                    assert result.exit_code == 0


# ------------------------------------------------------------------
# 测试 FetchResult / FetchSummary
# ------------------------------------------------------------------

class TestFetchSummary:
    def test_total_articles(self) -> None:
        from ainews.fetcher.runner import FetchResult, FetchSummary

        summary = FetchSummary(results=[
            FetchResult(source="a", articles=[MagicMock(), MagicMock()]),
            FetchResult(source="b", articles=[MagicMock()]),
        ])
        assert summary.total_articles == 3

    def test_success_failure_count(self) -> None:
        from ainews.fetcher.runner import FetchResult, FetchSummary

        summary = FetchSummary(results=[
            FetchResult(source="a", ok=True),
            FetchResult(source="b", ok=False, error="fail"),
            FetchResult(source="c", ok=True),
        ])
        assert summary.success_count == 2
        assert summary.failure_count == 1


# ------------------------------------------------------------------
# 测试 Registry
# ------------------------------------------------------------------

class TestRegistry:
    def test_list_sources(self) -> None:
        from ainews.fetcher.registry import list_sources
        sources = list_sources()
        assert "hackernews" in sources
        assert "arxiv" in sources
        assert "rss" in sources

    def test_get_fetcher(self) -> None:
        from ainews.fetcher.registry import get_fetcher
        from ainews.fetcher.hackernews import HackerNewsFetcher

        f = get_fetcher("hackernews")
        assert isinstance(f, HackerNewsFetcher)

    def test_get_unknown_fetcher(self) -> None:
        from ainews.fetcher.registry import get_fetcher

        with pytest.raises(KeyError, match="未知数据源"):
            get_fetcher("nonexistent")

    def test_is_registered(self) -> None:
        from ainews.fetcher.registry import is_registered

        assert is_registered("hackernews") is True
        assert is_registered("unknown") is False
