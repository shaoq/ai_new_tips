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
    source_type: str = typer.Argument(help="源类型: rss / arxiv"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="源名称"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="源 URL（RSS）"),
    categories: Optional[str] = typer.Option(
        None, "--categories", "-c", help="分类（ArXiv，逗号分隔）"
    ),
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

    else:
        console.print(f"[red]不支持的源类型: {source_type}[/red]")
        console.print("[dim]支持的类型: rss, arxiv[/dim]")
        raise typer.Exit(1)


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
    from ainews.config.loader import get_config, save_config, clear_config_cache, set_config_value

    config = get_config()

    # 映射 source_name 到配置路径
    source_map = {
        "hackernews": "sources.hackernews",
        "arxiv": "sources.arxiv",
        "rss": "sources.rss",
        "reddit": "sources.reddit",
        "github": "sources.github",
        "huggingface": "sources.huggingface",
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
    source_name: str = typer.Argument(help="源名称（如 hackernews, arxiv, rss）"),
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
