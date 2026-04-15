"""采集编排器 — 根据参数选择数据源并依次执行."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from rich.console import Console  # NOTE: 进度输出依赖，项目已有 rich 依赖

from ainews.fetcher.registry import get_fetcher, list_sources
from ainews.storage.database import init_db
from ainews.storage.models import Article

logger = logging.getLogger(__name__)
_console = Console()


@dataclass
class FetchResult:
    """单个源的采集结果."""

    source: str
    ok: bool = True
    articles: list[Article] = field(default_factory=list)
    error: str = ""
    elapsed_ms: int = 0


@dataclass
class FetchSummary:
    """采集汇总."""

    results: list[FetchResult] = field(default_factory=list)

    @property
    def total_articles(self) -> int:
        return sum(len(r.articles) for r in self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.ok)


def run_fetch(
    sources: Optional[list[str]] = None,
    backfill_days: Optional[int] = None,
    force: bool = False,
    dry_run: bool = False,
) -> FetchSummary:
    """执行采集.

    Args:
        sources: 指定数据源列表，None 表示全部已注册源
        backfill_days: 回填天数
        force: 忽略水印强制全量拉取
        dry_run: 预览模式，不实际入库

    Returns:
        FetchSummary 汇总结果
    """
    import time

    # 确保数据库已初始化
    init_db()

    if sources is None:
        sources = list_sources()

    summary = FetchSummary()

    for source_name in sources:
        try:
            fetcher = get_fetcher(source_name)
        except KeyError as e:
            logger.error("数据源 %s 未注册: %s", source_name, e)
            summary.results.append(FetchResult(source=source_name, ok=False, error=str(e)))
            continue

        start = time.monotonic()
        try:
            articles = fetcher.fetch(
                backfill_days=backfill_days,
                force=force,
                dry_run=dry_run,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            result = FetchResult(
                source=source_name,
                ok=True,
                articles=articles,
                elapsed_ms=elapsed,
            )
            logger.info(
                "[%s] 采集完成: %d 篇文章, 耗时 %dms",
                source_name, len(articles), elapsed,
            )
            _console.print(
                f"    [dim]·[/dim] {source_name}: [cyan]{len(articles)}[/cyan] articles ({elapsed}ms)"
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            result = FetchResult(
                source=source_name,
                ok=False,
                error=str(e),
                elapsed_ms=elapsed,
            )
            logger.error("[%s] 采集失败: %s", source_name, e, exc_info=True)
            _console.print(
                f"    [red]✗[/red] {source_name}: failed ({elapsed}ms)"
            )

        summary.results.append(result)

    logger.info(
        "采集汇总: %d/%d 成功, 共 %d 篇文章",
        summary.success_count, len(summary.results), summary.total_articles,
    )
    return summary
