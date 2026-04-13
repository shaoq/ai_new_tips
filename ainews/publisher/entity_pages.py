"""实体页面同步到 Obsidian Vault."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import (
    normalize_entity_name,
    render_entity_page,
)
from ainews.storage.models import Article, ArticleEntity, Entity

logger = logging.getLogger(__name__)

# 实体类型到目录的映射
ENTITY_TYPE_DIRS: dict[str, str] = {
    "person": "People",
    "company": "Companies",
    "project": "Projects",
}

# 不创建页面的实体类型
SKIP_TYPES = {"technology"}


def sync_entity_pages(
    session: Session,
    client: ObsidianClient,
) -> tuple[int, int]:
    """同步所有实体页面到 Obsidian.

    Returns:
        (created_count, updated_count)
    """
    # 查询所有实体
    statement = select(Entity)
    entities = session.exec(statement).all()

    if not entities:
        logger.info("没有实体需要同步")
        return 0, 0

    logger.info("开始同步 %d 个实体页面", len(entities))
    created = 0
    updated = 0

    for entity in entities:
        if entity.type in SKIP_TYPES:
            continue

        try:
            is_created = _sync_single_entity(session, client, entity)
            if is_created:
                created += 1
            else:
                updated += 1
        except Exception as exc:
            logger.error(
                "同步实体失败 [name=%s]: %s", entity.name, exc
            )

    logger.info("实体同步完成: %d 创建, %d 更新", created, updated)
    return created, updated


def _sync_single_entity(
    session: Session,
    client: ObsidianClient,
    entity: Entity,
) -> bool:
    """同步单个实体页面.

    Returns:
        True 表示新创建, False 表示更新
    """
    entity_name = normalize_entity_name(entity.name)
    if not entity_name:
        logger.warning("实体名称规范化后为空: %s", entity.name)
        return False

    dir_name = ENTITY_TYPE_DIRS.get(entity.type)
    if not dir_name:
        logger.debug("跳过未支持类型: %s (%s)", entity.name, entity.type)
        return False

    path = f"AI-News/Entities/{dir_name}/{entity_name}.md"

    # 查询关联文章
    articles = _get_entity_articles(session, entity.id)

    if client.degraded:
        return _sync_entity_filesystem(client, entity, articles, path)
    else:
        return _sync_entity_rest(client, entity, articles, path)


def _sync_entity_rest(
    client: ObsidianClient,
    entity: Entity,
    articles: list[Article],
    path: str,
) -> bool:
    """REST API 模式同步实体页面."""
    # 检查页面是否存在
    search_results = client.search_simple(normalize_entity_name(entity.name))

    exists = any(
        r.get("path", "").endswith(f"/{normalize_entity_name(entity.name)}.md")
        for r in search_results
    )

    if exists:
        # 更新 frontmatter
        fields: dict[str, Any] = {
            "mention_count": entity.mention_count,
        }
        if articles:
            last_date = articles[0].published_at
            if last_date:
                fields["last_seen"] = last_date.strftime("%Y-%m-%d")

        client.patch_frontmatter(path, fields)
        logger.debug("实体页面更新 (REST): %s", path)
        return False
    else:
        # 创建新页面
        content = render_entity_page(entity, articles)
        client.put_vault_file(path, content)
        logger.debug("实体页面创建 (REST): %s", path)
        return True


def _sync_entity_filesystem(
    client: ObsidianClient,
    entity: Entity,
    articles: list[Article],
    path: str,
) -> bool:
    """文件系统降级模式同步实体页面."""
    full_path = client.vault_path / path
    entity_name = normalize_entity_name(entity.name)

    if full_path.exists():
        # 更新 frontmatter
        try:
            content = full_path.read_text(encoding="utf-8")
            updated = _update_entity_frontmatter(content, entity, articles)
            full_path.write_text(updated, encoding="utf-8")
            logger.debug("实体页面更新 (文件系统): %s", path)
            return False
        except OSError as exc:
            logger.error("更新实体页面失败: %s", exc)
            return False
    else:
        # 创建新页面
        content = render_entity_page(entity, articles)
        success = client.put_vault_file(path, content)
        if success:
            logger.debug("实体页面创建 (文件系统): %s", path)
        return success


def _get_entity_articles(
    session: Session, entity_id: int
) -> list[Article]:
    """获取实体关联的文章列表."""
    statement = (
        select(Article)
        .join(ArticleEntity, ArticleEntity.article_id == Article.id)
        .where(ArticleEntity.entity_id == entity_id)
        .order_by(Article.published_at.desc())
    )
    return list(session.exec(statement).all())


def _update_entity_frontmatter(
    content: str,
    entity: Entity,
    articles: list[Article],
) -> str:
    """更新实体页面的 frontmatter 字段."""
    # 解析现有 frontmatter
    import yaml

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return content

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return content

    # 更新字段
    fm["mention_count"] = entity.mention_count
    if articles and articles[0].published_at:
        fm["last_seen"] = articles[0].published_at.strftime("%Y-%m-%d")

    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    body = content[match.end():]
    return f"---\n{new_fm}---{body}"
