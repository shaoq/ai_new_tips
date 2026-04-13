"""测试 launchd 管理."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ainews.scheduler.launchd import (
    launchctl_load,
    launchctl_unload,
    launchctl_kickstart,
    launchctl_list,
    write_plist,
    delete_plist,
    get_ainews_plist_files,
)


class TestLaunchctlLoad:
    """launchctl load 测试."""

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_load_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, err = launchctl_load(Path("/test.plist"))
        assert ok is True
        assert err == ""
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "launchctl"
        assert args[1] == "load"

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_load_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="already loaded")
        ok, err = launchctl_load(Path("/test.plist"))
        assert ok is False
        assert "already loaded" in err


class TestLaunchctlUnload:
    """launchctl unload 测试."""

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_unload_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, err = launchctl_unload(Path("/test.plist"))
        assert ok is True

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_unload_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not loaded")
        ok, err = launchctl_unload(Path("/test.plist"))
        assert ok is False


class TestLaunchctlKickstart:
    """launchctl kickstart 测试."""

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_kickstart_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, err = launchctl_kickstart("com.ainews.morning")
        assert ok is True
        args = mock_run.call_args[0][0]
        assert "kickstart" in args
        assert "com.ainews.morning" in args[-1]

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_kickstart_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not loaded")
        ok, err = launchctl_kickstart("com.ainews.morning")
        assert ok is False


class TestLaunchctlList:
    """launchctl list 状态解析测试."""

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_parse_list_output(self, mock_run: MagicMock) -> None:
        output = (
            "-\t0\tcom.ainews.morning\n"
            "12345\t0\tcom.ainews.noon\n"
            "-\t78\tcom.ainews.evening\n"
            "999\t0\tcom.apple.dock\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=output)

        statuses = launchctl_list()
        assert "com.ainews.morning" in statuses
        assert statuses["com.ainews.morning"].loaded is True
        assert statuses["com.ainews.morning"].pid is None
        assert statuses["com.ainews.noon"].pid == 12345
        assert statuses["com.ainews.evening"].last_exit == 78
        assert "com.apple.dock" not in statuses

    @patch("ainews.scheduler.launchd.subprocess.run")
    def test_empty_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        statuses = launchctl_list()
        assert statuses == {}


class TestPlistIO:
    """plist 文件读写测试."""

    def test_write_plist(self, tmp_path: Path) -> None:
        plist_path = tmp_path / "test.plist"
        write_plist(plist_path, "<plist>test</plist>")
        assert plist_path.exists()
        assert plist_path.read_text() == "<plist>test</plist>"

    def test_write_creates_parent(self, tmp_path: Path) -> None:
        plist_path = tmp_path / "sub" / "dir" / "test.plist"
        write_plist(plist_path, "content")
        assert plist_path.exists()

    def test_delete_existing(self, tmp_path: Path) -> None:
        plist_path = tmp_path / "test.plist"
        plist_path.write_text("content")
        assert delete_plist(plist_path) is True
        assert not plist_path.exists()

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        assert delete_plist(tmp_path / "nope.plist") is False


class TestGetAinewsPlistFiles:
    """get_ainews_plist_files 测试."""

    @patch("ainews.scheduler.launchd.Path")
    def test_finds_plist_files(self, mock_path_cls: MagicMock) -> None:
        mock_dir = MagicMock()
        mock_path_cls.home.return_value.__truediv__.return_value.__truediv__.return_value = mock_dir
        mock_dir.exists.return_value = True
        mock_file = MagicMock()
        mock_file.name = "com.ainews.morning.plist"
        mock_dir.glob.return_value = [mock_file]

        files = get_ainews_plist_files()
        assert len(files) == 1
