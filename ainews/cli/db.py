"""CLI db 子命令."""

from __future__ import annotations

import typer
from rich.table import Table
from rich.console import Console

from ainews.storage.database import get_db_path, init_db, get_session

db_app = typer.Typer(help="数据库管理", no_args_is_help=True)


@db_app.command("status")
def db_status() -> None:
    """显示数据库状态."""
    db_path = get_db_path()
    console = Console()

    table = Table(title="数据库状态")
    table.add_column("属性", style="cyan")
    table.add_column("值", style="green")

    table.add_row("路径", str(db_path))

    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        table.add_row("大小", f"{size_mb:.2f} MB")
        table.add_row("状态", "已存在")

        init_db()
        with get_session() as session:
            from sqlmodel import text
            tables = ["articles", "source_metrics", "fetch_log", "entities", "article_entities", "clusters", "push_log"]
            for t in tables:
                try:
                    result = session.exec(text(f"SELECT COUNT(*) FROM {t}"))  # noqa: S608
                    count = result.one()
                    table.add_row(f"  {t}", str(count))
                except Exception:
                    table.add_row(f"  {t}", "未创建")
    else:
        table.add_row("状态", "未创建（首次运行时自动创建）")

    console.print(table)
