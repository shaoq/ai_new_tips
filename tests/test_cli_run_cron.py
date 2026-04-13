"""测试 CLI run 和 cron 命令."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ainews.cli.main import app

runner = CliRunner()


class TestRunCommand:
    """ainews run 命令测试."""

    def test_run_help(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "skip-push" in result.output

    @patch("ainews.cli.run._step_fetch", return_value=5)
    @patch("ainews.cli.run._step_process", return_value=3)
    @patch("ainews.cli.run._step_dedup", return_value=0)
    @patch("ainews.cli.run._step_trend", return_value=2)
    @patch("ainews.cli.run._step_sync", return_value=3)
    @patch("ainews.cli.run._step_push", return_value=1)
    def test_run_dry_run(self, mock_push, mock_sync, mock_trend, mock_dedup, mock_process, mock_fetch) -> None:
        result = runner.invoke(app, ["run", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output or "Pipeline Summary" in result.output

    @patch("ainews.cli.run.PipelineRunner")
    def test_run_with_skip_push(self, mock_runner_cls: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.has_failures = False
        mock_result.steps = []
        mock_result.total_duration = 1.0
        mock_runner = MagicMock()
        mock_runner.run.return_value = mock_result
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["run", "--skip-push"])
        assert result.exit_code == 0

    @patch("ainews.cli.run.PipelineRunner")
    def test_run_with_failures_exits_1(self, mock_runner_cls: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.has_failures = True
        mock_result.steps = []
        mock_result.total_duration = 1.0
        mock_runner = MagicMock()
        mock_runner.run.return_value = mock_result
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1


class TestCronCommands:
    """ainews cron 命令测试."""

    def test_cron_help(self) -> None:
        result = runner.invoke(app, ["cron", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output
        assert "uninstall" in result.output
        assert "list" in result.output
        assert "pause" in result.output
        assert "resume" in result.output
        assert "trigger" in result.output

    @patch("ainews.cli.cron.get_schedules")
    @patch("ainews.cli.cron.write_plist")
    @patch("ainews.cli.cron.launchctl_load")
    def test_cron_install(self, mock_load, mock_write, mock_schedules) -> None:
        from ainews.scheduler.templates import ScheduleConfig
        mock_schedules.return_value = [
            ScheduleConfig(
                name="morning", label="com.ainews.morning",
                command_args=["ainews", "run"], hour=8, minute=0,
                log_path="/tmp/ainews-morning.log", err_path="/tmp/ainews-morning.err",
            )
        ]
        mock_load.return_value = (True, "")

        result = runner.invoke(app, ["cron", "install"])
        assert result.exit_code == 0
        assert "morning" in result.output

    @patch("ainews.cli.cron.get_ainews_plist_files")
    def test_cron_list_empty(self, mock_files) -> None:
        mock_files.return_value = []
        result = runner.invoke(app, ["cron", "list"])
        assert result.exit_code == 0
        assert "未安装" in result.output

    @patch("ainews.cli.cron.launchctl_kickstart")
    @patch("ainews.cli.cron.launchctl_list")
    def test_cron_trigger_not_loaded(self, mock_list, mock_kickstart) -> None:
        mock_list.return_value = {}
        result = runner.invoke(app, ["cron", "trigger", "--name", "morning"])
        assert result.exit_code == 1
        assert "未加载" in result.output

    @patch("ainews.cli.cron.launchctl_kickstart")
    @patch("ainews.cli.cron.launchctl_list")
    def test_cron_trigger_success(self, mock_list, mock_kickstart) -> None:
        from ainews.scheduler.launchd import LaunchdStatus
        mock_list.return_value = {
            "com.ainews.morning": LaunchdStatus(label="com.ainews.morning", loaded=True, pid=123),
        }
        mock_kickstart.return_value = (True, "")
        result = runner.invoke(app, ["cron", "trigger", "--name", "morning"])
        assert result.exit_code == 0
        assert "triggered" in result.output
