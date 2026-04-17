"""CLI process 命令：处理文章."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ainews.llm.client import LLMClient
from ainews.processor.processor import ArticleProcessor, ProcessResult

app = typer.Typer(help="处理文章：分类、摘要、评分、实体提取")
console = Console()


def _create_processor() -> tuple[ArticleProcessor, "Session"]:
    """创建 ArticleProcessor 和数据库 session."""
    from ainews.config.loader import get_config
    from ainews.storage.database import get_session, init_db

    config = get_config()
    init_db(config)

    llm_client = LLMClient(config.llm)
    processor = ArticleProcessor(llm_client)
    session = get_session(config)
    return processor, session


@app.callback(invoke_without_command=True)
def process_callback(
    article: Optional[int] = typer.Option(
        None, "--article", "-a", help="处理指定 ID 的单篇文章"
    ),
    all_articles: bool = typer.Option(
        False, "--all", help="处理所有文章（需配合 --force）"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="强制重新处理"
    ),
    backfill_title_zh: bool = typer.Option(
        False, "--backfill-title-zh", help="回填已处理但 title_zh 为空的文章"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="限制处理数量（默认50，0=不限制）"
    ),
) -> None:
    """处理文章：分类、摘要、评分、实体提取、标签生成.

    无参数: 处理所有未处理的文章（默认50篇）
    --limit 0: 不限制，处理全部
    --limit 100: 处理100篇
    --article <id>: 处理指定 ID 的文章
    --all --force: 强制重新处理所有文章
    --backfill-title-zh: 回填已处理文章的中文标题
    """
    processor, ctx_mgr = _create_processor()
    # None=未传(用默认50), 0=不限制, >0=指定数量
    batch_limit: int | None = limit

    with ctx_mgr as session:
        try:
            if article is not None:
                _process_single(processor, session, article)
            elif backfill_title_zh:
                _backfill_title_zh(processor, session, batch_limit)
            elif all_articles and force:
                _process_all_force(processor, session)
            else:
                _process_unprocessed(processor, session, batch_limit)
        finally:
            pass


def _process_single(
    processor: ArticleProcessor, session: "Session", article_id: int
) -> None:
    """处理单篇文章并输出详细结果."""
    result = processor.process_by_id(session, article_id)

    if result is None:
        console.print(f"[red]文章 ID {article_id} 不存在[/red]")
        raise typer.Exit(code=1)

    if not result.success:
        console.print(f"[red]处理失败: {result.error}[/red]")
        raise typer.Exit(code=1)

    console.print("[green]处理成功[/green]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("字段", style="cyan")
    table.add_column("值")
    table.add_row("文章 ID", str(result.article_id))
    table.add_row("分类", result.category)
    table.add_row("中文摘要", result.summary_zh)
    table.add_row("相关性评分", str(result.relevance))
    table.add_row("标签", ", ".join(result.tags))
    console.print(table)


def _process_unprocessed(
    processor: ArticleProcessor, session: "Session", limit: int | None = None
) -> None:
    """处理未处理文章并输出统计."""
    results = processor.process_unprocessed(session, limit=limit)
    _print_batch_summary(results, "增量处理")


def _process_all_force(
    processor: ArticleProcessor, session: "Session"
) -> None:
    """强制处理所有文章并输出统计."""
    results = processor.process_all_force(session)
    _print_batch_summary(results, "强制全量处理")


def _backfill_title_zh(
    processor: ArticleProcessor, session: "Session", limit: int | None
) -> None:
    """回填已处理文章的中文标题."""
    results = processor.backfill_title_zh(session, limit=limit)
    _print_batch_summary(results, "title_zh 回填")


def _print_batch_summary(results: list[ProcessResult], mode: str) -> None:
    """输出批量处理结果摘要."""
    if not results:
        console.print("[yellow]没有需要处理的文章[/yellow]")
        return

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    console.print(f"\n[bold]{mode}完成[/bold]")
    console.print(f"  成功: [green]{success_count}[/green] 篇")
    if fail_count > 0:
        console.print(f"  失败: [red]{fail_count}[/red] 篇")

        fail_table = Table(show_header=True, header_style="bold red")
        fail_table.add_column("文章 ID")
        fail_table.add_column("错误")
        for r in results:
            if not r.success:
                fail_table.add_row(str(r.article_id), r.error)
        console.print(fail_table)
