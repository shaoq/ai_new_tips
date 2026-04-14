"""CLI sources 子命令 — ainews sources 管理."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ainews.fetcher.registry import get_fetcher, list_sources

sources_app = typer.Typer(help="数据源管理", no_args_is_help=True)


@sources_app.command("list")
def sources_list() -> None:
    """列出所有已注册数据源及状态."""
    console = Console()

    table = Table(title="数据源列表")
    table.add_column("名称", style="cyan")
    table.add_column("状态")

    for name in list_sources():
        try:
            fetcher = get_fetcher(name)
            result = fetcher.test_connection()
            if result.get("ok"):
                status = f"[green]可用[/green] ({result.get('latency_ms', '?')}ms)"
            else:
                status = f"[red]不可用[/red] ({result.get('error', 'unknown')})"
        except Exception as e:
            status = f"[red]错误[/red] ({e})"
        table.add_row(name, status)

    console.print(table)


@sources_app.command("add")
def sources_add(
    source_type: str = typer.Argument(help="源类型: rss / arxiv / reddit / hf-papers / github-trending / chinese"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="源名称"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="源 URL（RSS）"),
    categories: Optional[str] = typer.Option(
        None, "--categories", "-c", help="分类（ArXiv，逗号分隔）"
    ),
    # Reddit 专用参数
    subreddit: Optional[str] = typer.Option(None, "--subreddit", help="Reddit subreddit 名称（可重复）"),
    client_id: Optional[str] = typer.Option(None, "--client-id", help="Reddit OAuth2 client_id"),
    client_secret: Optional[str] = typer.Option(None, "--client-secret", help="Reddit OAuth2 client_secret"),
    user_agent: Optional[str] = typer.Option(None, "--user-agent", help="Reddit user agent"),
    # HFPapers 专用参数
    min_upvotes: Optional[int] = typer.Option(None, "--min-upvotes", help="HFPapers 最低 upvotes（默认 10）"),
    # GitHub 专用参数
    topic: Optional[str] = typer.Option(None, "--topic", help="GitHub topic（可重复，逗号分隔）"),
    language: Optional[str] = typer.Option(None, "--language", help="GitHub language（可重复，逗号分隔）"),
    min_stars: Optional[int] = typer.Option(None, "--min-stars", help="GitHub 最低 stars（默认 50）"),
    token: Optional[str] = typer.Option(None, "--token", help="GitHub Personal Access Token"),
    # Chinese 专用参数
    method: Optional[str] = typer.Option(None, "--method", help="中文源方式: rss / scrape"),
) -> None:
    """添加数据源."""
    console = Console()

    if source_type == "rss":
        if not name or not url:
            console.print("[red]RSS 源需要 --name 和 --url 参数[/red]")
            raise typer.Exit(1)

        # 验证 URL 可达
        from ainews.fetcher.rss import RSSFetcher
        rss = RSSFetcher()
        result = rss.test_feed(url)
        if not result.get("ok"):
            console.print(f"[red]RSS URL 验证失败: {result.get('error')}[/red]")
            raise typer.Exit(1)

        # 添加到配置
        from ainews.config.loader import get_config, save_config, clear_config_cache
        config = get_config()
        config.sources.rss.keywords = list(set(config.sources.rss.keywords + [name]))
        save_config(config)
        clear_config_cache()
        console.print(f"[green]已添加 RSS 源: {name} ({url})[/green]")

    elif source_type == "arxiv":
        cats = categories.split(",") if categories else ["cs.AI", "cs.LG", "cs.CL"]
        console.print(f"[green]ArXiv 分类已设置: {', '.join(cats)}[/green]")
        console.print("[dim]提示: 使用 ainews config set 修改 ArXiv 分类[/dim]")

    elif source_type == "reddit":
        _add_reddit(console, subreddit, client_id, client_secret, user_agent)

    elif source_type == "hf-papers":
        _add_hf_papers(console, min_upvotes)

    elif source_type == "github-trending":
        _add_github(console, topic, language, min_stars, token)

    elif source_type == "chinese":
        _add_chinese(console, name, url, method)

    else:
        console.print(f"[red]不支持的源类型: {source_type}[/red]")
        console.print("[dim]支持的类型: rss, arxiv, reddit, hf-papers, github-trending, chinese[/dim]")
        raise typer.Exit(1)


def _add_reddit(
    console: Console,
    subreddit: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    user_agent: Optional[str],
) -> None:
    """添加 Reddit 源配置."""
    from ainews.config.loader import get_config, save_config, clear_config_cache

    config = get_config()
    reddit = config.sources.reddit

    if subreddit:
        # 支持逗号分隔
        new_subs = [s.strip() for s in subreddit.split(",")]
        existing = set(reddit.subreddits)
        reddit = reddit.model_copy(update={
            "subreddits": list(existing | set(new_subs)),
        })

    if client_id:
        reddit = reddit.model_copy(update={"client_id": client_id})
    if client_secret:
        reddit = reddit.model_copy(update={"client_secret": client_secret})
    if user_agent:
        reddit = reddit.model_copy(update={"user_agent": user_agent})

    config = config.model_copy(update={
        "sources": config.sources.model_copy(update={"reddit": reddit}),
    })
    save_config(config)
    clear_config_cache()
    console.print(f"[green]Reddit 配置已更新[/green]")
    console.print(f"  Subreddits: {', '.join(reddit.subreddits)}")
    console.print(f"  Client ID: {'已设置' if reddit.client_id else '未设置'}")


def _add_hf_papers(console: Console, min_upvotes: Optional[int]) -> None:
    """添加 HuggingFace Papers 源配置."""
    from ainews.config.loader import get_config, save_config, clear_config_cache

    config = get_config()
    hf = config.sources.hf_papers

    if min_upvotes is not None:
        hf = hf.model_copy(update={"min_upvotes": min_upvotes})

    config = config.model_copy(update={
        "sources": config.sources.model_copy(update={"hf_papers": hf}),
    })
    save_config(config)
    clear_config_cache()
    console.print(f"[green]HuggingFace Papers 配置已更新[/green]")
    console.print(f"  Min upvotes: {hf.min_upvotes}")


def _add_github(
    console: Console,
    topic: Optional[str],
    language: Optional[str],
    min_stars: Optional[int],
    token: Optional[str],
) -> None:
    """添加 GitHub Trending 源配置."""
    from ainews.config.loader import get_config, save_config, clear_config_cache

    config = get_config()
    gh = config.sources.github

    updates: dict = {}
    if topic:
        new_topics = [t.strip() for t in topic.split(",")]
        updates["topics"] = list(set(gh.topics) | set(new_topics))
    if language:
        new_langs = [l.strip() for l in language.split(",")]
        updates["languages"] = list(set(gh.languages) | set(new_langs))
    if min_stars is not None:
        updates["min_stars"] = min_stars
    if token:
        updates["token"] = token

    if updates:
        gh = gh.model_copy(update=updates)

    config = config.model_copy(update={
        "sources": config.sources.model_copy(update={"github": gh}),
    })
    save_config(config)
    clear_config_cache()
    console.print(f"[green]GitHub Trending 配置已更新[/green]")
    console.print(f"  Topics: {', '.join(gh.topics)}")
    console.print(f"  Languages: {', '.join(gh.languages)}")
    console.print(f"  Min stars: {gh.min_stars}")
    console.print(f"  Token: {'已设置' if gh.token else '未设置'}")


def _add_chinese(
    console: Console,
    name: Optional[str],
    url: Optional[str],
    method: Optional[str],
) -> None:
    """添加中文源配置."""
    from ainews.config.loader import get_config, save_config, clear_config_cache
    from ainews.config.settings import ChineseSourceConfig

    if not name or not url:
        console.print("[red]中文源需要 --name 和 --url 参数[/red]")
        raise typer.Exit(1)

    if not method:
        method = "rss"

    if method not in ("rss", "scrape"):
        console.print(f"[red]不支持的 method: {method}，请使用 rss 或 scrape[/red]")
        raise typer.Exit(1)

    config = get_config()
    new_source = ChineseSourceConfig(name=name, url=url, method=method)

    existing = config.sources.chinese.sources
    # 如果同名源已存在，替换
    sources = [s for s in existing if s.name != name]
    sources.append(new_source)

    chinese = config.sources.chinese.model_copy(update={"sources": sources})
    config = config.model_copy(update={
        "sources": config.sources.model_copy(update={"chinese": chinese}),
    })
    save_config(config)
    clear_config_cache()
    console.print(f"[green]已添加中文源: {name} ({url}, {method})[/green]")


@sources_app.command("remove")
def sources_remove(
    source_name: str = typer.Argument(help="源名称（如 rss:openai-blog）"),
) -> None:
    """移除数据源."""
    console = Console()

    if source_name.startswith("rss:"):
        feed_name = source_name[4:]
        from ainews.config.loader import get_config, save_config, clear_config_cache
        config = get_config()
        keywords = config.sources.rss.keywords
        if feed_name in keywords:
            config.sources.rss.keywords = [k for k in keywords if k != feed_name]
            save_config(config)
            clear_config_cache()
            console.print(f"[green]已移除 RSS 源: {feed_name}[/green]")
        else:
            console.print(f"[yellow]RSS 源不存在: {feed_name}[/yellow]")
    elif source_name.startswith("chinese:"):
        src_name = source_name[8:]
        from ainews.config.loader import get_config, save_config, clear_config_cache
        config = get_config()
        sources = [s for s in config.sources.chinese.sources if s.name != src_name]
        chinese = config.sources.chinese.model_copy(update={"sources": sources})
        config = config.model_copy(update={
            "sources": config.sources.model_copy(update={"chinese": chinese}),
        })
        save_config(config)
        clear_config_cache()
        console.print(f"[green]已移除中文源: {src_name}[/green]")
    else:
        console.print(f"[yellow]移除 {source_name}: 请使用配置文件管理[/yellow]")


@sources_app.command("enable")
def sources_enable(
    source_name: str = typer.Argument(help="源名称"),
) -> None:
    """启用数据源."""
    console = Console()
    _set_source_enabled(source_name, True)
    console.print(f"[green]已启用: {source_name}[/green]")


@sources_app.command("disable")
def sources_disable(
    source_name: str = typer.Argument(help="源名称"),
) -> None:
    """禁用数据源."""
    console = Console()
    _set_source_enabled(source_name, False)
    console.print(f"[green]已禁用: {source_name}[/green]")


def _set_source_enabled(source_name: str, enabled: bool) -> None:
    """通过配置设置数据源启用/禁用状态."""
    from ainews.config.loader import get_config, save_config, clear_config_cache

    config = get_config()

    # 映射 source_name 到配置路径
    source_map = {
        "hackernews": "sources.hackernews",
        "arxiv": "sources.arxiv",
        "rss": "sources.rss",
        "reddit": "sources.reddit",
        "hf_papers": "sources.hf_papers",
        "github": "sources.github",
        "chinese": "sources.chinese",
    }

    config_path = source_map.get(source_name)
    if config_path is None:
        console = Console()
        console.print(f"[yellow]未知数据源: {source_name}[/yellow]")
        raise typer.Exit(1)

    data = config.model_dump()
    keys = config_path.split(".")
    target = data
    for key in keys:
        target = target[key]
    target["enabled"] = enabled

    config = type(config)(**data)
    save_config(config)
    clear_config_cache()


@sources_app.command("test")
def sources_test(
    source_name: str = typer.Argument(help="源名称（如 hackernews, arxiv, rss, reddit, hf_papers, github, chinese）"),
) -> None:
    """测试数据源连通性."""
    console = Console()

    try:
        fetcher = get_fetcher(source_name)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"测试 [cyan]{source_name}[/cyan] 连通性...")
    result = fetcher.test_connection()

    if result.get("ok"):
        console.print(f"[green]连接成功[/green]")
        console.print(f"  延迟: {result.get('latency_ms', '?')}ms")
        console.print(f"  详情: {result.get('detail', '')}")
    else:
        console.print(f"[red]连接失败[/red]")
        console.print(f"  错误: {result.get('error', 'unknown')}")
        raise typer.Exit(1)
