"""CLI sync obsidian 子命令."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

logger = logging.getLogger(__name__)

sync_app = typer.Typer(
    name="sync",
    help="同步数据到外部系统",
    add_completion=False,
    no_args_is_help=True,
)


@sync_app.command()
def obsidian(
    test: bool = typer.Option(False, "--test", help="测试 Obsidian 连接和配置"),
    init_dashboards: bool = typer.Option(
        False, "--init-dashboards", help="初始化仪表盘模板"
    ),
    sync_entities: bool = typer.Option(
        False, "--sync-entities", help="同步实体页面"
    ),
    rebuild_dashboards: bool = typer.Option(
        False, "--rebuild-dashboards", help="重建仪表盘（覆盖已有）"
    ),
) -> None:
    """同步数据到 Obsidian Vault."""
    from ainews.config.loader import get_config
    from ainews.publisher.obsidian_client import ObsidianClient

    config = get_config()
    obs_config = config.obsidian

    # --test 模式
    if test:
        _run_test(obs_config)
        return

    # 验证配置
    if not obs_config.vault_path:
        typer.echo("错误: 未配置 obsidian.vault_path，请运行 ainews config set")
        raise typer.Exit(1)

    vault_path = Path(obs_config.vault_path)
    if not vault_path.exists():
        typer.echo(f"错误: vault_path 不存在: {vault_path}")
        raise typer.Exit(1)

    # 创建客户端
    client = ObsidianClient(
        api_key=obs_config.api_key,
        port=obs_config.port,
        vault_path=obs_config.vault_path,
    )

    with client:
        # 健康检查
        client.health_check()
        mode_label = "文件系统" if client.degraded else "REST API"
        typer.echo(f"同步模式: {mode_label}")

        # --init-dashboards 模式
        if init_dashboards:
            from ainews.publisher.dashboards import init_dashboards as do_init

            created, skipped = do_init(client)
            typer.echo(f"仪表盘初始化完成: {created} 创建, {skipped} 跳过")
            return

        # --rebuild-dashboards 模式
        if rebuild_dashboards:
            from ainews.publisher.dashboards import rebuild_dashboards as do_rebuild

            created, skipped = do_rebuild(client)
            typer.echo(f"仪表盘重建完成: {created} 创建, {skipped} 跳过")
            return

        # --sync-entities 模式
        if sync_entities:
            from ainews.storage.database import get_session

            with get_session(config) as session:
                from ainews.publisher.entity_pages import sync_entity_pages

                created, updated = sync_entity_pages(session, client)
                typer.echo(f"实体同步完成: {created} 创建, {updated} 更新")
            return

        # 默认模式: 完整同步（文章 -> 每日笔记 -> 实体页面）
        _run_full_sync(client, config)


def _run_test(obs_config: Any) -> None:
    """执行连接测试和配置验证."""
    from ainews.publisher.obsidian_client import ObsidianClient

    typer.echo("=== Obsidian 连接测试 ===\n")

    # 检查 vault_path
    if not obs_config.vault_path:
        typer.echo("[FAIL] obsidian.vault_path 未配置")
    else:
        vault_path = Path(obs_config.vault_path)
        if vault_path.exists():
            typer.echo(f"[ OK ] vault_path 存在: {vault_path}")
        else:
            typer.echo(f"[FAIL] vault_path 不存在: {vault_path}")

    # 检查 api_key
    if not obs_config.api_key:
        typer.echo("[FAIL] obsidian.api_key 未配置")
    else:
        masked = f"***{obs_config.api_key[-4:]}" if len(obs_config.api_key) >= 4 else "***"
        typer.echo(f"[ OK ] api_key 已配置: {masked}")

    # 检查 REST API 连接
    if obs_config.api_key:
        client = ObsidianClient(
            api_key=obs_config.api_key,
            port=obs_config.port,
            vault_path=obs_config.vault_path,
        )
        with client:
            healthy = client.health_check()
            if healthy:
                typer.echo(f"[ OK ] REST API 连接成功 (port={obs_config.port})")
            else:
                typer.echo(f"[FAIL] REST API 连接失败 (port={obs_config.port})")
                typer.echo("       将使用文件系统降级模式")
    else:
        typer.echo("[SKIP] 跳过 REST API 测试（api_key 未配置）")

    typer.echo("\n测试完成.")


def _run_full_sync(client: Any, config: Any) -> None:
    """执行完整同步: 文章 -> 每日笔记 -> 实体页面."""
    from ainews.publisher.article_sync import sync_articles
    from ainews.publisher.daily_note import sync_daily_note
    from ainews.storage.database import get_session

    with get_session(config) as session:
        # 1. 同步文章
        typer.echo("正在同步文章...")
        synced, skipped = sync_articles(session, client)
        typer.echo(f"文章同步: {synced} 成功, {skipped} 跳过")

        # 获取本次同步的文章用于每日笔记
        from sqlmodel import select
        from datetime import datetime

        from ainews.storage.models import Article

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        synced_articles = session.exec(
            select(Article).where(
                Article.obsidian_synced == True,  # noqa: E712
                Article.imported_at >= today_start,
            )
        ).all()

        # 2. 追加每日笔记
        if synced_articles:
            typer.echo("正在更新每日笔记...")
            success = sync_daily_note(client, list(synced_articles))
            if success:
                typer.echo("每日笔记更新成功")
            else:
                typer.echo("每日笔记更新失败")

        # 3. 同步实体页面
        typer.echo("正在同步实体页面...")
        from ainews.publisher.entity_pages import sync_entity_pages

        created, updated = sync_entity_pages(session, client)
        typer.echo(f"实体同步: {created} 创建, {updated} 更新")

    typer.echo("同步完成.")
