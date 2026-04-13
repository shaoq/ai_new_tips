"""CLI entities 命令：管理实体库."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import select

from ainews.storage.database import get_session, init_db
from ainews.storage.models import Entity
from ainews.trend.entity_discovery import discover_entities


def entities_command(
    days: int = typer.Option(7, "--days", "-d", help="显示最近 N 天的实体"),
    limit: int = typer.Option(20, "--limit", "-l", help="显示数量"),
    entity_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="按类型过滤: person/company/project/technology"
    ),
    new_only: bool = typer.Option(False, "--new-only", help="仅显示新实体"),
    discover: bool = typer.Option(False, "--discover", help="执行实体发现"),
) -> None:
    """管理实体库：列出、发现实体."""
    console = Console()
    init_db()

    with get_session() as session:
        # 如果指定 --discover，先执行发现
        if discover:
            console.print("[bold]执行实体发现...[/bold]")
            results = discover_entities(session)
            new_count = sum(1 for r in results if r["is_new"])
            console.print(f"  发现 {len(results)} 个实体, {new_count} 个新实体\n")

        # 构建查询
        from datetime import datetime, timedelta

        since = datetime.utcnow() - timedelta(days=days)
        statement = select(Entity).where(Entity.first_seen_at >= since)

        if entity_type:
            statement = statement.where(Entity.type == entity_type)

        if new_only:
            statement = statement.where(Entity.is_new == True)  # noqa: E712

        statement = statement.order_by(Entity.mention_count.desc()).limit(limit)
        entities = list(session.exec(statement).all())

        if not entities:
            console.print("[yellow]没有找到匹配的实体[/yellow]")
            return

        # 输出表格
        table = Table(
            title=f"实体列表 (最近 {days} 天, 最多 {limit} 条)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("名称", style="white")
        table.add_column("类型", style="magenta")
        table.add_column("提及次数", justify="right", style="green")
        table.add_column("新?", style="yellow")
        table.add_column("首次发现", style="dim")

        for entity in entities:
            is_new_str = "[green]NEW[/green]" if entity.is_new else ""
            first_seen = (
                entity.first_seen_at.strftime("%Y-%m-%d")
                if entity.first_seen_at
                else ""
            )
            table.add_row(
                str(entity.id),
                entity.name,
                entity.type,
                str(entity.mention_count),
                is_new_str,
                first_seen,
            )

        console.print(table)
