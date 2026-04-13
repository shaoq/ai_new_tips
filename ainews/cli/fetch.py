"""CLI fetch 子命令 — ainews fetch."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ainews.fetcher.runner import run_fetch

fetch_app = typer.Typer(help="数据采集", no_args_is_help=True)


@fetch_app.command("run")
def fetch_run(
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="指定数据源（逗号分隔），不指定则采集全部"
    ),
    backfill: Optional[int] = typer.Option(
        None, "--backfill", "-b", help="回填天数（如 7 表示回填最近 7 天）"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="忽略水印，强制全量拉取"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="预览模式，不实际入库"
    ),
) -> None:
    """执行数据采集."""
    console = Console()

    sources = None
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]

    console.print(f"[bold cyan]开始采集[/bold cyan]")
    if sources:
        console.print(f"  数据源: {', '.join(sources)}")
    if backfill:
        console.print(f"  回填天数: {backfill}")
    if force:
        console.print("  [yellow]强制模式（忽略水印）[/yellow]")
    if dry_run:
        console.print("  [yellow]预览模式（不入库）[/yellow]")
    console.print()

    summary = run_fetch(
        sources=sources,
        backfill_days=backfill,
        force=force,
        dry_run=dry_run,
    )

    # 显示结果表格
    table = Table(title="采集结果")
    table.add_column("数据源", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("新文章", justify="right")
    table.add_column("耗时(ms)", justify="right")
    table.add_column("错误", style="red")

    for r in summary.results:
        status = "[green]OK[/green]" if r.ok else "[red]FAIL[/red]"
        count = str(len(r.articles)) if r.ok else "-"
        table.add_row(
            r.source,
            status,
            count,
            str(r.elapsed_ms),
            r.error[:60] if r.error else "",
        )

    table.add_section()
    table.add_row(
        "[bold]合计[/bold]",
        f"[bold]{summary.success_count}/{len(summary.results)}[/bold]",
        f"[bold]{summary.total_articles}[/bold]",
        "",
        "",
    )

    console.print(table)


# 兼容：fetch 直接作为命令使用
fetch_command = fetch_run
