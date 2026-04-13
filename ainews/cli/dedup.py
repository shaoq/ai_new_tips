"""CLI dedup 命令：执行标题相似度去重."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ainews.storage.database import get_session, init_db
from ainews.trend.dedup import dedup_articles, get_dedup_stats


def dedup_command(
    threshold: float = typer.Option(0.9, "--threshold", "-t", help="相似度阈值"),
    days: int = typer.Option(7, "--days", "-d", help="扫描最近 N 天"),
) -> None:
    """执行标题相似度去重."""
    console = Console()
    init_db()

    console.print(f"[bold]开始去重扫描[/bold] (阈值={threshold}, 最近 {days} 天)")

    with get_session() as session:
        duplicates = dedup_articles(session, days=days, threshold=threshold)

        # 输出结果
        console.print(f"\n检测到 {len(duplicates)} 对重复文章:")

        if duplicates:
            table = Table(show_header=True, header_style="bold")
            table.add_column("文章 A ID", style="cyan", justify="right")
            table.add_column("文章 B ID", style="cyan", justify="right")
            table.add_column("相似度", style="green", justify="right")

            for id_a, id_b, sim in duplicates:
                table.add_row(str(id_a), str(id_b), f"{sim:.4f}")

            console.print(table)

        # 统计信息
        stats = get_dedup_stats(session)
        console.print(f"\n[bold]统计:[/bold]")
        console.print(f"  总文章数: {stats['total']}")
        console.print(f"  重复文章: {stats['duplicate']}")
        console.print(f"  唯一文章: {stats['unique']}")
