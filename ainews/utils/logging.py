"""日志系统：按日归档 + latest.log 软链接."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import logging.handlers


_LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """初始化日志系统.

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_dir: 日志目录，默认 ~/.ainews/logs/
    """
    if log_dir is None:
        log_dir = Path.home() / ".ainews" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{today}.log"
    latest_link = log_dir / "latest.log"

    # 配置根 logger
    root_logger = logging.getLogger("ainews")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handler（避免重复）
    root_logger.handlers.clear()

    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # 更新 latest.log 软链接
    _update_latest_link(latest_link, log_file)


def _update_latest_link(link_path: Path, target: Path) -> None:
    """更新 latest.log 软链接指向当天日志文件."""
    try:
        if link_path.is_symlink() or link_path.exists():
            link_path.unlink()
        os.symlink(target, link_path)
    except OSError:
        pass  # 软链接创建失败不影响日志功能


def set_log_level(level: str) -> None:
    """动态切换日志级别."""
    root_logger = logging.getLogger("ainews")
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(log_level)
