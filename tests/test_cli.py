"""测试 CLI 命令：config init/show/set、db status、doctor."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ainews.cli.main import app

runner = CliRunner()


class TestMainApp:
    """主命令测试."""

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "ainews" in result.output
        assert "0.1.0" in result.output

    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "config" in result.output
        assert "db" in result.output
        assert "doctor" in result.output


class TestConfigShow:
    """config show 测试."""

    def test_config_show(self, tmp_path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("llm:\n  model: test-model\n  api_key: sk-secret-key-1234\n")
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["config", "show"])
            assert result.exit_code == 0


class TestConfigSet:
    """config set 测试."""

    def test_config_set(self, tmp_path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("llm:\n  model: gpt-4o\n  api_key: ''\n")
        with patch("ainews.config.loader.DEFAULT_CONFIG_PATH", config_path):
            from ainews.config.loader import clear_config_cache
            clear_config_cache()
            result = runner.invoke(app, ["config", "set", "llm.model", "claude-3"])
            assert result.exit_code == 0


class TestDbStatus:
    """db status 测试."""

    def test_db_status_no_db(self, tmp_path) -> None:
        from ainews.config.settings import AppConfig
        config = AppConfig()
        with patch("ainews.storage.database.get_db_path", return_value=tmp_path / "nonexistent.db"):
            result = runner.invoke(app, ["db", "status"])
            assert result.exit_code == 0
            assert "未创建" in result.output


class TestDoctor:
    """doctor 命令测试."""

    def test_doctor(self) -> None:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Python" in result.output
