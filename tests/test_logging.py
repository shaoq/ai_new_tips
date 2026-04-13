"""测试日志系统."""

from __future__ import annotations

import logging
from pathlib import Path

from ainews.utils.logging import setup_logging, set_log_level, _update_latest_link


class TestSetupLogging:
    """日志初始化测试."""

    def test_setup_creates_log_dir(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir)
        assert log_dir.exists()

    def test_setup_creates_log_file(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir)
        logger = logging.getLogger("ainews")
        logger.info("test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

    def test_setup_creates_latest_link(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir)
        latest = log_dir / "latest.log"
        assert latest.is_symlink() or latest.exists()

    def test_setup_default_level_info(self, tmp_path: Path) -> None:
        setup_logging(log_dir=tmp_path)
        logger = logging.getLogger("ainews")
        assert logger.level == logging.INFO

    def test_setup_debug_level(self, tmp_path: Path) -> None:
        setup_logging(level="DEBUG", log_dir=tmp_path)
        logger = logging.getLogger("ainews")
        assert logger.level == logging.DEBUG

    def test_setup_case_insensitive_level(self, tmp_path: Path) -> None:
        setup_logging(level="debug", log_dir=tmp_path)
        logger = logging.getLogger("ainews")
        assert logger.level == logging.DEBUG

    def test_clear_handlers_on_reinit(self, tmp_path: Path) -> None:
        setup_logging(log_dir=tmp_path)
        logger = logging.getLogger("ainews")
        count1 = len(logger.handlers)
        setup_logging(log_dir=tmp_path)
        assert len(logger.handlers) == count1


class TestSetLogLevel:
    """日志级别切换测试."""

    def test_set_level_debug(self) -> None:
        set_log_level("DEBUG")
        logger = logging.getLogger("ainews")
        assert logger.level == logging.DEBUG

    def test_set_level_warning(self) -> None:
        set_log_level("WARNING")
        logger = logging.getLogger("ainews")
        assert logger.level == logging.WARNING

    def test_set_level_case_insensitive(self) -> None:
        set_log_level("error")
        logger = logging.getLogger("ainews")
        assert logger.level == logging.ERROR


class TestLatestLink:
    """软链接测试."""

    def test_create_link(self, tmp_path: Path) -> None:
        target = tmp_path / "2026-04-14.log"
        target.write_text("log content")
        link = tmp_path / "latest.log"

        _update_latest_link(link, target)
        assert link.is_symlink()

    def test_update_existing_link(self, tmp_path: Path) -> None:
        old_target = tmp_path / "old.log"
        old_target.write_text("old")
        link = tmp_path / "latest.log"

        _update_latest_link(link, old_target)
        assert link.is_symlink()

        new_target = tmp_path / "new.log"
        new_target.write_text("new")
        _update_latest_link(link, new_target)
        assert link.is_symlink()
