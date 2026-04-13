"""CLI doctor 命令 — 环境检查."""

from __future__ import annotations

import platform
import sys

import typer
from rich.console import Console
from rich.table import Table


def doctor_command() -> None:
    """检查运行环境."""
    console = Console()
    table = Table(title="环境检查")
    table.add_column("检查项", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("详情")

    # Python 版本
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 12)
    table.add_row(
        "Python 版本",
        "[green]OK[/green]" if py_ok else "[red]FAIL[/red]",
        f"{py_version} ({'>= 3.12' if py_ok else '< 3.12，需要升级'})",
    )

    # 配置文件
    from ainews.config.loader import get_config
    config = get_config()
    config_exists = config.config_path.exists()
    table.add_row(
        "配置文件",
        "[green]OK[/green]" if config_exists else "[yellow]MISSING[/yellow]",
        str(config.config_path) if config_exists else "运行 ainews config init 创建",
    )

    # 数据库
    db_exists = config.db_path.exists()
    if db_exists:
        try:
            from ainews.storage.database import init_db
            init_db()
            table.add_row("数据库", "[green]OK[/green]", str(config.db_path))
        except Exception as e:
            table.add_row("数据库", "[red]FAIL[/red]", str(e))
    else:
        table.add_row("数据库", "[yellow]MISSING[/yellow]", "首次运行时自动创建")

    # Obsidian REST API（可选）
    if config.obsidian.api_key and config.obsidian.vault_path:
        try:
            import httpx
            url = f"https://127.0.0.1:{config.obsidian.port}"
            resp = httpx.get(url, headers={"Authorization": f"Bearer {config.obsidian.api_key}"}, verify=False, timeout=5)
            if resp.status_code == 200:
                table.add_row("Obsidian API", "[green]OK[/green]", f"端口 {config.obsidian.port}")
            else:
                table.add_row("Obsidian API", "[yellow]FAIL[/yellow]", f"状态码 {resp.status_code}")
        except Exception as e:
            table.add_row("Obsidian API", "[yellow]SKIP[/yellow]", f"无法连接: {type(e).__name__}")
    else:
        table.add_row("Obsidian API", "[dim]SKIP[/dim]", "未配置（可选）")

    console.print(table)
