"""launchd 管理：封装 launchctl 命令."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LaunchdStatus:
    """launchd 任务状态."""

    label: str
    loaded: bool
    pid: int | None = None
    last_exit: int | None = None


def launchctl_load(plist_path: Path) -> tuple[bool, str]:
    """加载 plist 文件."""
    try:
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "launchctl load timed out"
    except FileNotFoundError:
        return False, "launchctl not found"


def launchctl_unload(plist_path: Path) -> tuple[bool, str]:
    """卸载 plist 文件."""
    try:
        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "launchctl unload timed out"
    except FileNotFoundError:
        return False, "launchctl not found"


def launchctl_kickstart(label: str) -> tuple[bool, str]:
    """立即触发任务."""
    import os
    uid = os.getuid()
    target = f"gui/{uid}/{label}"
    try:
        result = subprocess.run(
            ["launchctl", "kickstart", target],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "launchctl kickstart timed out"


def launchctl_list() -> dict[str, LaunchdStatus]:
    """查询所有 ainews 任务的加载状态."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    statuses: dict[str, LaunchdStatus] = {}
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line or "com.ainews." not in line:
            continue
        parts = line.split()
        if len(parts) >= 3:
            pid_or_dash = parts[0]
            last_exit = parts[1]
            label = parts[2]
            if label.startswith("com.ainews."):
                statuses[label] = LaunchdStatus(
                    label=label,
                    loaded=True,
                    pid=int(pid_or_dash) if pid_or_dash != "-" else None,
                    last_exit=int(last_exit) if last_exit != "-" else None,
                )
    return statuses


def write_plist(plist_path: Path, content: str) -> None:
    """写入 plist 文件."""
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(content, encoding="utf-8")


def delete_plist(plist_path: Path) -> bool:
    """删除 plist 文件."""
    if plist_path.exists():
        plist_path.unlink()
        return True
    return False


def get_ainews_plist_files() -> list[Path]:
    """获取所有 ainews plist 文件."""
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    if not agents_dir.exists():
        return []
    return sorted(agents_dir.glob("com.ainews.*.plist"))
