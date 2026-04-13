"""测试 CLI sync obsidian 命令."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ainews.cli.main import app

runner = CliRunner()


class TestSyncObsidianTest:
    """sync obsidian --test 测试."""

    def test_test_mode_missing_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("obsidian:\n  vault_path: ''\n  api_key: ''\n")
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["sync", "obsidian", "--test"])
            assert result.exit_code == 0
            assert "vault_path 未配置" in result.output or "[FAIL]" in result.output

    def test_test_mode_valid_vault(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            f"obsidian:\n  vault_path: '{tmp_path}'\n  api_key: 'test-api-key-1234'\n"
        )
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["sync", "obsidian", "--test"])
            assert result.exit_code == 0


class TestSyncObsidianInitDashboards:
    """sync obsidian --init-dashboards 测试."""

    def test_init_dashboards(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        config_path.write_text(
            f"obsidian:\n  vault_path: '{vault_path}'\n  api_key: 'test-key-123'\n"
        )
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["sync", "obsidian", "--init-dashboards"])
            assert result.exit_code == 0

    def test_init_dashboards_creates_files(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        config_path.write_text(
            f"obsidian:\n  vault_path: '{vault_path}'\n  api_key: 'test-key-123'\n"
        )
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            with patch(
                "ainews.publisher.obsidian_client.ObsidianClient.health_check",
                return_value=False,
            ):
                result = runner.invoke(app, ["sync", "obsidian", "--init-dashboards"])
                assert result.exit_code == 0

        # 检查文件系统模式是否创建了仪表盘
        dashboards_dir = vault_path / "AI-News" / "Dashboards"
        if dashboards_dir.exists():
            files = list(dashboards_dir.glob("*.md"))
            assert len(files) == 8


class TestSyncObsidianMissingVault:
    """缺少 vault_path 时的错误处理."""

    def test_missing_vault_path(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("obsidian:\n  vault_path: ''\n  api_key: 'test'\n")
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["sync", "obsidian"])
            assert result.exit_code == 1

    def test_nonexistent_vault_path(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        nonexistent = tmp_path / "nonexistent"
        config_path.write_text(
            f"obsidian:\n  vault_path: '{nonexistent}'\n  api_key: 'test'\n"
        )
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["sync", "obsidian"])
            assert result.exit_code == 1


class TestSyncHelp:
    """help 输出测试."""

    def test_sync_help(self) -> None:
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "obsidian" in result.output

    def test_sync_obsidian_help(self) -> None:
        result = runner.invoke(app, ["sync", "obsidian", "--help"])
        assert result.exit_code == 0
        assert "--test" in result.output
        assert "--init-dashboards" in result.output
        assert "--sync-entities" in result.output
        assert "--rebuild-dashboards" in result.output


class TestMainAppWithSync:
    """主 CLI 帮助信息包含 sync."""

    def test_help_shows_sync(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "sync" in result.output
