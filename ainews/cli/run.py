"""CLI run 命令 — 一键执行完整流水线."""

from __future__ import annotations

from typing import Optional

import typer

from ainews.pipeline.runner import PipelineResult, PipelineRunner, PipelineStep, RunOptions, StepStatus

run_command = typer.Typer(help="运行完整流水线", no_args_is_help=False)


@run_command.callback(invoke_without_command=True)
def run(
    backfill: str = typer.Option("", "--backfill", help="回溯时间范围（如 7d、3h）"),
    source: str = typer.Option("", "--source", help="指定数据源（逗号分隔，如 hackernews,arxiv）"),
    no_push: bool = typer.Option(False, "--no-push", "--skip-push", help="跳过钉钉推送"),
    trending_only_push: bool = typer.Option(False, "--trending-only-push", help="仅推送热点文章"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="跳过 Obsidian 同步"),
    limit: int = typer.Option(0, "--limit", help="限制处理文章数量（默认50，0=不限制）"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用详细日志"),
    dry_run: bool = typer.Option(False, "--dry-run", help="模拟模式，不实际执行"),
) -> None:
    """一键执行完整流水线: fetch -> process -> dedup -> trend -> sync -> push."""
    if verbose:
        from ainews.utils.logging import set_log_level
        set_log_level("DEBUG")

    options = RunOptions(
        backfill=backfill,
        source=source,
        skip_sync=skip_sync,
        skip_push=no_push,
        trending_only_push=trending_only_push,
        dry_run=dry_run,
        verbose=verbose,
        limit=limit,
    )

    steps = _build_steps()
    runner = PipelineRunner(steps, options)

    typer.echo("Starting ainews pipeline...")
    result = runner.run()
    runner.print_summary(result)

    if result.has_failures:
        raise typer.Exit(1)


def _build_steps() -> list[PipelineStep]:
    """组装流水线步骤."""
    return [
        PipelineStep(
            name="Fetch",
            execute_fn=_step_fetch,
            dry_run_desc="Will fetch from configured sources",
        ),
        PipelineStep(
            name="Process",
            execute_fn=_step_process,
            dry_run_desc="Will process unprocessed articles via LLM",
        ),
        PipelineStep(
            name="Dedup",
            execute_fn=_step_dedup,
            skippable=True,
            dry_run_desc="Will deduplicate articles by title similarity",
        ),
        PipelineStep(
            name="Trend",
            execute_fn=_step_trend,
            dry_run_desc="Will analyze trends and score articles",
        ),
        PipelineStep(
            name="Sync Obsidian",
            execute_fn=_step_sync,
            skippable=True,
            dry_run_desc="Will sync articles and daily notes to Obsidian",
        ),
        PipelineStep(
            name="Push DingTalk",
            execute_fn=_step_push,
            skippable=True,
            dry_run_desc="Will push notifications to DingTalk",
        ),
    ]


def _step_fetch(options: RunOptions) -> int:
    """Fetch 步骤."""
    from ainews.fetcher.runner import run_fetch

    sources = options.source.split(",") if options.source else None
    backfill_days = int(options.backfill.rstrip("d")) if options.backfill else None
    summary = run_fetch(sources=sources, backfill_days=backfill_days)
    return summary.total_articles


def _step_process(options: RunOptions) -> int:
    """Process 步骤."""
    from ainews.processor.processor import ArticleProcessor
    from ainews.llm.client import LLMClient
    from ainews.config.loader import get_config
    from ainews.storage.database import init_db, get_session

    init_db()
    config = get_config()
    llm = LLMClient(config.llm)
    with get_session() as session:
        processor = ArticleProcessor(llm)
        limit = options.limit if options.limit > 0 else None  # None → 使用默认50
        results = processor.process_unprocessed(session, limit=limit)
        return len(results)


def _step_dedup(options: RunOptions) -> int:
    """Dedup 步骤."""
    from ainews.trend.dedup import dedup_articles
    from ainews.storage.database import init_db, get_session

    init_db()
    with get_session() as session:
        duplicates = dedup_articles(session)
        return len(duplicates)


def _step_trend(options: RunOptions) -> int:
    """Trend 分析步骤."""
    from ainews.trend.scorer import update_trend_scores
    from ainews.storage.database import init_db, get_session

    init_db()
    with get_session() as session:
        scores = update_trend_scores(session)
        return len(scores)


def _step_sync(options: RunOptions) -> int:
    """Obsidian 同步步骤."""
    from ainews.publisher.article_sync import sync_articles
    from ainews.publisher.daily_note import sync_daily_note
    from ainews.publisher.obsidian_client import ObsidianClient
    from ainews.config.loader import get_config
    from ainews.storage.database import init_db, get_session

    init_db()
    config = get_config()
    client = ObsidianClient(
        api_key=config.obsidian.api_key,
        port=config.obsidian.port,
        vault_path=config.obsidian.vault_path,
    )
    with get_session() as session:
        synced, skipped = sync_articles(session, client)
        sync_daily_note(client, [])
        return synced


def _step_push(options: RunOptions) -> int:
    """钉钉推送步骤."""
    from ainews.publisher.strategy import PushStrategy
    from ainews.publisher.dingtalk import DingTalkClient
    from ainews.publisher.formatter import build_feedcard
    from ainews.config.loader import get_config
    from ainews.storage.database import init_db, get_session

    init_db()
    config = get_config()
    with get_session() as session:
        strategy = PushStrategy(session)
        client = DingTalkClient(config.dingtalk.webhook_url, config.dingtalk.secret)

        if options.trending_only_push:
            articles = strategy.query_trending_articles()
        else:
            articles = strategy.query_morning_articles()

        if not articles:
            return 0

        article_dicts = [
            {"title": a.title, "url": a.url, "source_name": a.source_name, "trend_score": a.trend_score}
            for a in articles
        ]
        message = build_feedcard(article_dicts, title="AI News Update")
        client.send(message)
        return len(articles)
