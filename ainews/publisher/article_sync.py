"""文章同步到 Obsidian Vault."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import (
    generate_slug,
    render_article_body,
    render_article_frontmatter,
)
from ainews.storage.models import Article

logger = logging.getLogger(__name__)


def sync_articles(
    session: Session,
    client: ObsidianClient,
) -> tuple[int, int]:
    """同步文章到 Obsidian.

    查询 obsidian_synced=false 且 processed=true 且 status!='duplicate' 的文章,
    按 trend_score DESC 排序后逐篇写入.

    Returns:
        (synced_count, skipped_count)
    """
    # 查询待同步文章
    statement = (
        select(Article)
        .where(Article.obsidian_synced == False)  # noqa: E712
        .where(Article.processed == True)  # noqa: E712
        .where(Article.status != "duplicate")
        .order_by(Article.trend_score.desc())
    )
    articles = session.exec(statement).all()

    if not articles:
        logger.info("没有新文章需要同步")
        return 0, 0

    logger.info("开始同步 %d 篇文章到 Obsidian", len(articles))
    synced_count = 0
    skipped_count = 0

    for article in articles:
        try:
            success = _sync_single_article(session, client, article)
            if success:
                synced_count += 1
            else:
                skipped_count += 1
        except Exception as exc:
            logger.error("同步文章失败 [id=%s, title=%s]: %s", article.id, article.title, exc)
            skipped_count += 1

    logger.info("同步完成: %d 成功, %d 跳过", synced_count, skipped_count)
    return synced_count, skipped_count


def _sync_single_article(
    session: Session,
    client: ObsidianClient,
    article: Article,
) -> bool:
    """同步单篇文章到 Obsidian."""
    # 生成路径
    path = _build_article_path(article)

    if client.degraded:
        return _sync_article_filesystem(session, client, article, path)
    else:
        return _sync_article_rest(session, client, article, path)


def _sync_article_rest(
    session: Session,
    client: ObsidianClient,
    article: Article,
    path: str,
) -> bool:
    """REST API 模式同步文章."""
    # 生成完整 Markdown 内容
    frontmatter = render_article_frontmatter(article)
    body = render_article_body(article)
    content = f"{frontmatter}\n\n{body}"

    # PUT 写入/覆盖
    success = client.put_vault_file(path, content)
    if success:
        _mark_synced(session, article, path)
    return success


def _sync_article_filesystem(
    session: Session,
    client: ObsidianClient,
    article: Article,
    path: str,
) -> bool:
    """文件系统降级模式同步文章."""
    import pathlib

    full_path = client.vault_path / path

    # 文件已存在则跳过
    if full_path.exists():
        logger.info("文件已存在，跳过: %s", path)
        _mark_synced(session, article, path)
        return True

    # 生成完整 Markdown 内容
    frontmatter = render_article_frontmatter(article)
    body = render_article_body(article)
    content = f"{frontmatter}\n\n{body}"

    success = client.put_vault_file(path, content)
    if success:
        _mark_synced(session, article, path)
    return success


def update_article_frontmatter(
    client: ObsidianClient,
    article: Article,
) -> bool:
    """更新已同步文章的 frontmatter 动态字段.

    仅 REST API 模式下有效，更新 trend_score、platforms、is_trending.
    """
    if not article.obsidian_path:
        return False

    fields: dict[str, Any] = {
        "trend_score": article.trend_score,
        "is_trending": article.is_trending,
    }

    import json

    platforms = json.loads(article.platforms) if article.platforms else []
    if platforms:
        fields["platforms"] = platforms

    return client.patch_frontmatter(article.obsidian_path, fields)


def _build_article_path(article: Article) -> str:
    """构建文章文件路径: AI-News/{category}/{YYYY-MM-DD}-{slug}.md"""
    slug = generate_slug(article.title)
    date_prefix = _get_date_prefix(article.published_at)
    category = article.category or "inbox"
    filename = f"{date_prefix}{slug}.md"
    return f"AI-News/{category}/{filename}"


def _get_date_prefix(dt: datetime | None) -> str:
    """获取日期前缀."""
    if dt is None:
        return datetime.now().strftime("%Y-%m-%d-")
    return dt.strftime("%Y-%m-%d-")


def _mark_synced(session: Session, article: Article, path: str) -> None:
    """标记文章已同步."""
    article.obsidian_synced = True
    article.obsidian_path = path
    session.add(article)
    session.commit()
    logger.debug("标记已同步: %s -> %s", article.title, path)
