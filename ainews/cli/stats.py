"""CLI stats 命令组：统计查询子命令集."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import func, select

from ainews.storage.database import get_session, init_db
from ainews.storage.models import Article, Cluster, Entity, SourceMetric

stats_app = typer.Typer(help="统计查询", no_args_is_help=True)


@stats_app.command("today")
def stats_today() -> None:
    """今日概览：文章数、热点数、top 3 热点标题、新实体数."""
    console = Console()
    init_db()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    with get_session() as session:
        # 今日文章数
        articles = list(
            session.exec(
                select(Article).where(Article.fetched_at >= today_start)
            ).all()
        )
        total_articles = len(articles)

        # 热点数
        trending = [a for a in articles if a.is_trending]
        trending_count = len(trending)

        # Top 3 热点标题
        top_trending = sorted(trending, key=lambda a: a.trend_score, reverse=True)[:3]

        # 新实体数
        new_entities = list(
            session.exec(
                select(Entity).where(Entity.is_new == True, Entity.first_seen_at >= today_start)  # noqa: E712
            ).all()
        )
        new_entity_count = len(new_entities)

        # 输出
        table = Table(title="今日概览", show_header=True, header_style="bold")
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green", justify="right")

        table.add_row("文章数", str(total_articles))
        table.add_row("热点数", str(trending_count))
        table.add_row("新实体数", str(new_entity_count))

        console.print(table)

        if top_trending:
            console.print("\n[bold]Top 3 热点:[/bold]")
            for i, article in enumerate(top_trending, 1):
                console.print(
                    f"  {i}. [green]{article.trend_score:.1f}[/green] - {article.title}"
                )


@stats_app.command("weekly")
def stats_weekly() -> None:
    """本周概览：同 today 但时间范围 7 天，含趋势变化."""
    console = Console()
    init_db()

    week_ago = datetime.utcnow() - timedelta(days=7)

    with get_session() as session:
        articles = list(
            session.exec(
                select(Article).where(Article.fetched_at >= week_ago)
            ).all()
        )
        total_articles = len(articles)
        trending = [a for a in articles if a.is_trending]
        trending_count = len(trending)

        top_trending = sorted(trending, key=lambda a: a.trend_score, reverse=True)[:5]

        new_entities = list(
            session.exec(
                select(Entity).where(Entity.is_new == True, Entity.first_seen_at >= week_ago)  # noqa: E712
            ).all()
        )

        # 按来源统计
        by_source: dict[str, int] = {}
        for a in articles:
            by_source[a.source] = by_source.get(a.source, 0) + 1

        table = Table(title="本周概览", show_header=True, header_style="bold")
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green", justify="right")

        table.add_row("文章数", str(total_articles))
        table.add_row("热点数", str(trending_count))
        table.add_row("新实体数", str(len(new_entities)))

        console.print(table)

        if top_trending:
            console.print("\n[bold]Top 5 热点:[/bold]")
            for i, article in enumerate(top_trending, 1):
                console.print(
                    f"  {i}. [green]{article.trend_score:.1f}[/green] - {article.title}"
                )

        if by_source:
            console.print("\n[bold]来源分布:[/bold]")
            for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
                console.print(f"  {source}: {count}")


@stats_app.command("trending")
def stats_trending(
    days: int = typer.Option(1, "--days", "-d", help="时间范围（天）"),
    limit: int = typer.Option(20, "--limit", "-l", help="显示数量"),
) -> None:
    """热点排行：trend_score DESC, 默认 top 20."""
    console = Console()
    init_db()

    since = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        articles = list(
            session.exec(
                select(Article)
                .where(Article.fetched_at >= since)
                .where(Article.is_trending == True)  # noqa: E712
                .order_by(Article.trend_score.desc())
                .limit(limit)
            ).all()
        )

        if not articles:
            console.print("[yellow]没有热点文章[/yellow]")
            return

        table = Table(
            title=f"热点排行 (最近 {days} 天, top {limit})",
            show_header=True,
            header_style="bold",
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("分数", justify="right", style="green")
        table.add_column("来源", style="magenta")
        table.add_column("标题", style="white")

        for i, article in enumerate(articles, 1):
            table.add_row(
                str(i),
                f"{article.trend_score:.1f}",
                article.source,
                article.title[:80],
            )

        console.print(table)


@stats_app.command("by-source")
def stats_by_source(
    days: int = typer.Option(7, "--days", "-d", help="时间范围（天）"),
) -> None:
    """来源分布：各源文章数、热点数占比."""
    console = Console()
    init_db()

    since = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        articles = list(
            session.exec(
                select(Article).where(Article.fetched_at >= since)
            ).all()
        )

        if not articles:
            console.print("[yellow]没有文章数据[/yellow]")
            return

        # 按来源统计
        source_data: dict[str, dict[str, int]] = {}
        for a in articles:
            source = a.source or "unknown"
            if source not in source_data:
                source_data[source] = {"total": 0, "trending": 0}
            source_data[source]["total"] += 1
            if a.is_trending:
                source_data[source]["trending"] += 1

        table = Table(
            title=f"来源分布 (最近 {days} 天)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("来源", style="cyan")
        table.add_column("文章数", justify="right", style="green")
        table.add_column("热点数", justify="right", style="yellow")
        table.add_column("热点占比", justify="right")

        for source, data in sorted(
            source_data.items(), key=lambda x: x[1]["total"], reverse=True
        ):
            total = data["total"]
            trending = data["trending"]
            ratio = f"{trending / total * 100:.1f}%" if total > 0 else "0%"
            table.add_row(source, str(total), str(trending), ratio)

        console.print(table)


@stats_app.command("by-category")
def stats_by_category(
    days: int = typer.Option(7, "--days", "-d", help="时间范围（天）"),
) -> None:
    """分类分布：各类文章数统计."""
    console = Console()
    init_db()

    since = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        articles = list(
            session.exec(
                select(Article).where(Article.fetched_at >= since)
            ).all()
        )

        if not articles:
            console.print("[yellow]没有文章数据[/yellow]")
            return

        # 按分类统计
        category_data: dict[str, int] = {}
        for a in articles:
            category = a.category or "uncategorized"
            category_data[category] = category_data.get(category, 0) + 1

        table = Table(
            title=f"分类分布 (最近 {days} 天)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("分类", style="cyan")
        table.add_column("文章数", justify="right", style="green")
        table.add_column("占比", justify="right")

        total = len(articles)
        for category, count in sorted(
            category_data.items(), key=lambda x: x[1], reverse=True
        ):
            ratio = f"{count / total * 100:.1f}%" if total > 0 else "0%"
            table.add_row(category, str(count), ratio)

        console.print(table)


@stats_app.command("new-entities")
def stats_new_entities(
    days: int = typer.Option(7, "--days", "-d", help="时间范围（天）"),
    entity_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="按类型过滤"
    ),
) -> None:
    """新发现实体列表."""
    console = Console()
    init_db()

    since = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        statement = (
            select(Entity)
            .where(Entity.is_new == True)  # noqa: E712
            .where(Entity.first_seen_at >= since)
            .order_by(Entity.mention_count.desc())
        )

        if entity_type:
            statement = statement.where(Entity.type == entity_type)

        entities = list(session.exec(statement).all())

        if not entities:
            console.print("[yellow]没有新实体[/yellow]")
            return

        table = Table(
            title=f"新发现实体 (最近 {days} 天)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("名称", style="white")
        table.add_column("类型", style="magenta")
        table.add_column("提及次数", justify="right", style="green")
        table.add_column("首次发现", style="dim")

        for entity in entities:
            first_seen = (
                entity.first_seen_at.strftime("%Y-%m-%d")
                if entity.first_seen_at
                else ""
            )
            table.add_row(
                entity.name,
                entity.type,
                str(entity.mention_count),
                first_seen,
            )

        console.print(table)


@stats_app.command("top-people")
def stats_top_people(
    days: int = typer.Option(30, "--days", "-d", help="时间范围（天）"),
    limit: int = typer.Option(20, "--limit", "-l", help="显示数量"),
) -> None:
    """人物活跃度排行：mention_count DESC."""
    console = Console()
    init_db()

    since = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        people = list(
            session.exec(
                select(Entity)
                .where(Entity.type == "person")
                .where(Entity.first_seen_at >= since)
                .order_by(Entity.mention_count.desc())
                .limit(limit)
            ).all()
        )

        if not people:
            console.print("[yellow]没有人物数据[/yellow]")
            return

        table = Table(
            title=f"人物活跃度排行 (最近 {days} 天, top {limit})",
            show_header=True,
            header_style="bold",
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("名称", style="white")
        table.add_column("提及次数", justify="right", style="green")
        table.add_column("新?", style="yellow")
        table.add_column("首次发现", style="dim")

        for i, person in enumerate(people, 1):
            is_new_str = "[green]NEW[/green]" if person.is_new else ""
            first_seen = (
                person.first_seen_at.strftime("%Y-%m-%d")
                if person.first_seen_at
                else ""
            )
            table.add_row(
                str(i),
                person.name,
                str(person.mention_count),
                is_new_str,
                first_seen,
            )

        console.print(table)
