"""测试 CLI sources 扩展 — reddit / hf-papers / github-trending / chinese 添加命令."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ainews.cli.sources import sources_app


runner = CliRunner()


class TestSourcesAddReddit:
    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_reddit_with_subreddit(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig, RedditConfig, SourcesConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, [
            "add", "reddit",
            "--subreddit", "MachineLearning",
            "--client-id", "test_id",
            "--client-secret", "test_secret",
        ])

        assert result.exit_code == 0
        assert "Reddit" in result.output
        mock_save.assert_called_once()

    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_reddit_multiple_subreddits(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, [
            "add", "reddit",
            "--subreddit", "MachineLearning,LocalLLaMA",
        ])

        assert result.exit_code == 0
        mock_save.assert_called_once()


class TestSourcesAddHFPapers:
    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_hf_papers_default(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, ["add", "hf-papers"])

        assert result.exit_code == 0
        assert "HuggingFace" in result.output

    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_hf_papers_with_min_upvotes(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, [
            "add", "hf-papers",
            "--min-upvotes", "25",
        ])

        assert result.exit_code == 0
        assert "25" in result.output


class TestSourcesAddGithub:
    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_github_default(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, ["add", "github-trending"])

        assert result.exit_code == 0
        assert "GitHub" in result.output

    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_github_with_params(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, [
            "add", "github-trending",
            "--topic", "deep-learning",
            "--language", "python",
            "--min-stars", "100",
            "--token", "ghp_test123",
        ])

        assert result.exit_code == 0
        assert "GitHub" in result.output
        assert "100" in result.output


class TestSourcesAddChinese:
    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_chinese_rss(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, [
            "add", "chinese",
            "--name", "qbitai",
            "--url", "https://www.qbitai.com/",
            "--method", "rss",
        ])

        assert result.exit_code == 0
        assert "qbitai" in result.output

    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_add_chinese_scrape(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import AppConfig
        mock_get.return_value = AppConfig()

        result = runner.invoke(sources_app, [
            "add", "chinese",
            "--name", "36kr",
            "--url", "https://www.36kr.com/",
            "--method", "scrape",
        ])

        assert result.exit_code == 0
        assert "36kr" in result.output

    def test_add_chinese_missing_name(self) -> None:
        result = runner.invoke(sources_app, [
            "add", "chinese",
            "--url", "https://www.qbitai.com/",
        ])

        assert result.exit_code == 1

    def test_add_chinese_missing_url(self) -> None:
        result = runner.invoke(sources_app, [
            "add", "chinese",
            "--name", "qbitai",
        ])

        assert result.exit_code == 1

    def test_add_chinese_invalid_method(self) -> None:
        result = runner.invoke(sources_app, [
            "add", "chinese",
            "--name", "test",
            "--url", "http://test.com",
            "--method", "invalid",
        ])

        assert result.exit_code == 1


class TestSourcesAddUnsupported:
    def test_unsupported_type(self) -> None:
        result = runner.invoke(sources_app, ["add", "unsupported"])
        assert result.exit_code == 1
        assert "不支持" in result.output


class TestSourcesRemoveChinese:
    @patch("ainews.config.loader.save_config")
    @patch("ainews.config.loader.get_config")
    def test_remove_chinese_source(self, mock_get: MagicMock, mock_save: MagicMock) -> None:
        from ainews.config.settings import (
            AppConfig,
            ChineseConfig,
            ChineseSourceConfig,
            SourcesConfig,
        )
        config = AppConfig(
            sources=SourcesConfig(
                chinese=ChineseConfig(
                    sources=[
                        ChineseSourceConfig(name="qbitai", url="https://qbitai.com", method="rss"),
                        ChineseSourceConfig(name="36kr", url="https://36kr.com", method="scrape"),
                    ],
                ),
            ),
        )
        mock_get.return_value = config

        result = runner.invoke(sources_app, ["remove", "chinese:qbitai"])

        assert result.exit_code == 0
        assert "qbitai" in result.output
        mock_save.assert_called_once()
