"""CLI push 子命令：ainews push dingtalk."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import typer
from rich import print as rprint
from sqlmodel import Session

from ainews.config.loader import get_config
from ainews.publisher.dingtalk import DingTalkClient
from ainews.publisher.formatter import (
    build_actioncard,
    build_feedcard,
    build_markdown_noon,
    build_markdown_weekly,
    build_test_message,
)
from ainews.publisher.strategy import PushStrategy
from ainews.storage.database import get_session
from ainews.storage.models import Article, PushLog

logger = logging.getLogger(__name__)

push_app = typer.Typer(help="推送通知", no_args_is_help=True)


@push_app.command("dingtalk")
def push_dingtalk(
    trending_only: bool = typer.Option(False, "--trending-only", help="仅推送热点文章 (trend_score >= 8)"),
    weekly: bool = typer.Option(False, "--weekly", help="推送本周周报"),
    test: bool = typer.Option(False, "--test", help="发送测试消息验证连通性"),
    format: Optional[str] = typer.Option(None, "--format", help="强制消息格式: feedcard|markdown"),
    article: Optional[str] = typer.Option(None, "--article", help="推送指定文章（URL 或标题关键词）"),
) -> None:
    """推送消息到钉钉群聊."""
    config = get_config()

    if not config.dingtalk.webhook_url or not config.dingtalk.secret:
        rprint("[red]错误: 钉钉未配置。请运行 ainews config set dingtalk.webhook_url <url>[/red]")
        raise typer.Exit(1)

    client = DingTalkClient(
        webhook_url=config.dingtalk.webhook_url,
        secret=config.dingtalk.secret,
    )

    # --test 选项
    if test:
        _send_test(client)
        return

    # --weekly 选项
    if weekly:
        _send_weekly(client)
        return

    # --article 选项
    if article:
        _send_article(client, article)
        return

    # --trending-only 选项
    if trending_only:
        _send_trending(client, format)
        return

    # 默认模式：按时间段自动选择
    _send_auto(client, format)


def _send_test(client: DingTalkClient) -> None:
    """发送测试消息."""
    try:
        message = build_test_message()
        client.send(message)
        rprint("[green]测试消息发送成功！钉钉 Webhook 连通正常。[/green]")
    except Exception as e:
        rprint(f"[red]测试消息发送失败: {e}[/red]")
        raise typer.Exit(1) from e


def _send_weekly(client: DingTalkClient) -> None:
    """发送周报."""
    with get_session() as session:
        strategy = PushStrategy(session)
        stats = strategy.query_weekly_stats()
        top_articles = strategy.query_weekly_top_articles(limit=5)

        if stats["total"] == 0:
            rprint("[yellow]本周无文章数据，跳过周报推送。[/yellow]")
            return

        articles_data = [_article_to_dict(a) for a in top_articles]
        message = build_markdown_weekly(stats, articles_data)

        try:
            client.send(message)
            rprint(f"[green]周报推送成功！本周共 {stats['total']} 篇文章。[/green]")
        except Exception as e:
            rprint(f"[red]周报推送失败: {e}[/red]")
            raise typer.Exit(1) from e


def _send_article(client: DingTalkClient, slug: str) -> None:
    """推送指定文章."""
    with get_session() as session:
        strategy = PushStrategy(session)
        article_obj = strategy.query_article_by_slug(slug)

        if article_obj is None:
            rprint(f"[red]未找到匹配文章: {slug}[/red]")
            raise typer.Exit(1)

        message = build_actioncard(_article_to_dict(article_obj))

        try:
            result = client.send(message)
            _record_push(session, article_obj, "actioncard", "")
            session.commit()
            rprint(f"[green]文章推送成功: {article_obj.title}[/green]")
        except Exception as e:
            logger.error("文章推送失败: %s - %s", article_obj.title, e)
            rprint(f"[red]推送失败: {e}[/red]")
            raise typer.Exit(1) from e


def _send_trending(client: DingTalkClient, format_override: Optional[str]) -> None:
    """推送热点文章."""
    with get_session() as session:
        strategy = PushStrategy(session)
        articles = strategy.query_trending_articles()

        if not articles:
            rprint("[yellow]当前无热点文章可推送。[/yellow]")
            return

        if format_override == "markdown":
            articles_data = [_article_to_dict(a) for a in articles]
            message = build_markdown_noon(articles_data)
            push_type = "markdown"
        else:
            # 默认用 actionCard 逐篇推送热点
            _send_trending_actioncards(client, session, strategy, articles)
            return

        try:
            client.send(message)
            for a in articles:
                _record_push(session, a, push_type, "")
            session.commit()
            rprint(f"[green]热点推送成功！共 {len(articles)} 篇。[/green]")
        except Exception as e:
            logger.error("热点推送失败: %s", e)
            rprint(f"[red]推送失败: {e}[/red]")
            raise typer.Exit(1) from e


def _send_trending_actioncards(
    client: DingTalkClient,
    session: Session,
    strategy: PushStrategy,
    articles: list[Article],
) -> None:
    """逐篇推送 actionCard 热点."""
    pushed = 0
    for article in articles:
        if not strategy.should_push(article, "actioncard"):
            continue

        message = build_actioncard(_article_to_dict(article))
        try:
            client.send(message)
            _record_push(session, article, "actioncard", "")
            session.commit()
            pushed += 1
            rprint(f"  推送: {article.title}")
        except Exception as e:
            logger.error("推送失败: %s - %s", article.title, e)
            rprint(f"  [red]失败: {article.title} - {e}[/red]")

    rprint(f"[green]热点推送完成！成功 {pushed} 篇。[/green]")


def _send_auto(client: DingTalkClient, format_override: Optional[str]) -> None:
    """按时间段自动选择推送格式."""
    now = datetime.now()
    hour = now.hour

    # 确定推送模式
    if 6 <= hour < 11:
        mode = "morning_digest"
    elif 11 <= hour < 15:
        mode = "noon_update"
    else:
        mode = "evening_digest"

    with get_session() as session:
        strategy = PushStrategy(session)

        if mode == "morning_digest":
            _do_morning_push(client, session, strategy, format_override)
        elif mode == "noon_update":
            _do_noon_push(client, session, strategy, format_override)
        else:
            _do_evening_push(client, session, strategy, format_override)


def _do_morning_push(
    client: DingTalkClient,
    session: Session,
    strategy: PushStrategy,
    format_override: Optional[str],
) -> None:
    """晨报推送 (feedCard, Top 10)."""
    articles = strategy.query_morning_articles(limit=10)

    if not articles:
        rprint("[yellow]当前无新文章可推送。[/yellow]")
        return

    articles_data = [_article_to_dict(a) for a in articles]
    message = build_feedcard(articles_data, title="AI 晨报")

    try:
        client.send(message)
        for a in articles:
            _record_push(session, a, "feedcard", "")
        session.commit()
        rprint(f"[green]晨报推送成功！共 {len(articles)} 篇。[/green]")
    except Exception as e:
        logger.error("晨报推送失败: %s", e)
        rprint(f"[red]推送失败: {e}[/red]")
        raise typer.Exit(1) from e


def _do_noon_push(
    client: DingTalkClient,
    session: Session,
    strategy: PushStrategy,
    format_override: Optional[str],
) -> None:
    """午间速报 (markdown, 热点)."""
    if strategy.should_skip_noon():
        rprint("[yellow]午间无新热点，跳过推送。[/yellow]")
        return

    articles = strategy.query_noon_articles()
    articles_data = [_article_to_dict(a) for a in articles]

    if format_override == "feedcard":
        message = build_feedcard(articles_data, title="午间热点")
        push_type = "feedcard"
    else:
        message = build_markdown_noon(articles_data)
        push_type = "markdown"

    try:
        client.send(message)
        for a in articles:
            _record_push(session, a, push_type, "")
        session.commit()
        rprint(f"[green]午间速报推送成功！共 {len(articles)} 条热点。[/green]")
    except Exception as e:
        logger.error("午间推送失败: %s", e)
        rprint(f"[red]推送失败: {e}[/red]")
        raise typer.Exit(1) from e


def _do_evening_push(
    client: DingTalkClient,
    session: Session,
    strategy: PushStrategy,
    format_override: Optional[str],
) -> None:
    """晚报推送 (feedCard, 全量)."""
    articles = strategy.query_evening_articles()

    if not articles:
        rprint("[yellow]当前无新文章可推送。[/yellow]")
        return

    articles_data = [_article_to_dict(a) for a in articles]

    if format_override == "markdown":
        message = build_markdown_noon(articles_data)
        push_type = "markdown"
    else:
        message = build_feedcard(articles_data, title="AI 晚报")
        push_type = "feedcard"

    try:
        client.send(message)
        for a in articles:
            _record_push(session, a, push_type, "")
        session.commit()
        rprint(f"[green]晚报推送成功！共 {len(articles)} 篇。[/green]")
    except Exception as e:
        logger.error("晚报推送失败: %s", e)
        rprint(f"[red]推送失败: {e}[/red]")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _article_to_dict(article: Article) -> dict[str, str | float]:
    """将 Article 对象转换为消息构建器所需的字典."""
    from ainews.publisher.source_map import get_favicon_url, get_source_type

    source_type = get_source_type(article.source)
    return {
        "title": article.title,
        "url": article.url,
        "summary_zh": article.summary_zh,
        "trend_score": article.trend_score,
        "source_name": article.source_name,
        "category": article.category,
        "source_type": source_type,
        "pic_url": get_favicon_url(article.source),
        "obsidian_url": "",  # Obsidian URL 需要从其他模块获取
    }


def _record_push(
    session: Session,
    article: Article,
    push_type: str,
    msg_id: str,
) -> None:
    """记录推送历史并更新文章状态.

    Args:
        session: 数据库 Session
        article: 文章对象
        push_type: 推送类型 (feedcard/actioncard/markdown/weekly)
        msg_id: 消息 ID
    """
    # 5.1 写入 push_log
    log = PushLog(
        article_id=article.id,
        push_type=push_type,
        msg_id=msg_id,
        pushed_at=datetime.now(),
    )
    session.add(log)

    # 5.2 更新 dingtalk_sent
    article.dingtalk_sent = True
    session.add(article)
