"""CLI trend 命令：执行完整趋势分析流水线."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ainews.storage.database import get_session, init_db
from ainews.trend.auto_discover import run_auto_discovery
from ainews.trend.correlator import CrossSourceCorrelator
from ainews.trend.entity_discovery import discover_entities
from ainews.trend.scorer import update_trend_scores
from ainews.trend.title_cluster import cluster_titles, save_clusters


def trend_command(
    days: int = typer.Option(1, "--days", "-d", help="分析最近 N 天的数据"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅输出分析结果，不写入数据库"),
) -> None:
    """执行完整趋势分析流水线（关联 -> 评分 -> 实体发现）."""
    console = Console()
    init_db()

    with get_session() as session:
        # Step 1: 跨源关联
        console.rule("[bold cyan]Step 1: 跨源关联[/bold cyan]")
        correlator = CrossSourceCorrelator(session)
        groups = correlator.correlate(days=days)
        console.print(f"  发现 {len(groups)} 个跨源关联组")

        if not dry_run:
            updated = correlator.update_platforms(groups)
            console.print(f"  更新了 {updated} 篇文章的 platforms 字段")

        # Step 2: 标题聚类
        console.rule("[bold cyan]Step 2: 标题聚类[/bold cyan]")
        clusters = cluster_titles(session, days=days)
        console.print(f"  发现 {len(clusters)} 个标题聚类")

        if not dry_run:
            saved = save_clusters(session, clusters)
            console.print(f"  写入 {saved} 条聚类记录")

        # Step 3: 趋势评分
        console.rule("[bold cyan]Step 3: 趋势评分[/bold cyan]")
        scores = update_trend_scores(session, days=days, dry_run=dry_run)
        trending_count = sum(1 for s in scores if s["is_trending"])
        console.print(f"  评分完成: {len(scores)} 篇文章, {trending_count} 篇热点")

        # Step 4: 实体发现
        console.rule("[bold cyan]Step 4: 实体发现[/bold cyan]")
        entity_results = discover_entities(session)
        new_entity_count = sum(1 for e in entity_results if e["is_new"])
        console.print(f"  发现 {len(entity_results)} 个实体, {new_entity_count} 个新实体")

        # Step 5: 自动发现
        console.rule("[bold cyan]Step 5: 自动发现[/bold cyan]")
        discoveries = run_auto_discovery(session, days=days)
        console.print(f"  新兴研究员: {len(discoveries['researchers'])}")
        console.print(f"  新项目: {len(discoveries['projects'])}")
        console.print(f"  新公司: {len(discoveries['companies'])}")

        # 摘要
        console.rule("[bold green]分析摘要[/bold green]")
        summary_table = Table(show_header=True, header_style="bold")
        summary_table.add_column("指标", style="cyan")
        summary_table.add_column("数量", style="green", justify="right")

        summary_table.add_row("跨源关联组", str(len(groups)))
        summary_table.add_row("标题聚类", str(len(clusters)))
        summary_table.add_row("热点文章", str(trending_count))
        summary_table.add_row("新实体", str(new_entity_count))
        summary_table.add_row("新兴研究员", str(len(discoveries["researchers"])))
        summary_table.add_row("新项目", str(len(discoveries["projects"])))
        summary_table.add_row("新公司", str(len(discoveries["companies"])))

        if dry_run:
            summary_table.add_row("模式", "[yellow]DRY RUN (未写入)[/yellow]")

        console.print(summary_table)
