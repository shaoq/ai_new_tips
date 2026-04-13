"""实体发现引擎：从 LLM 提取结果中发现和追踪实体."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from ainews.storage.crud import get_or_create
from ainews.storage.models import Article, ArticleEntity, Entity

# 支持的实体类型
ENTITY_TYPES = {"person", "company", "project", "technology"}


def discover_entities(
    session: Session,
    article_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """从已处理文章的 entities JSON 字段提取实体列表.

    参数:
        session: 数据库会话
        article_ids: 指定文章 ID 列表，None 表示处理所有未处理实体的文章

    返回:
        发现结果列表 [{"entity_name": str, "entity_type": str, "is_new": bool, "article_id": int}, ...]
    """
    if article_ids:
        statement = select(Article).where(Article.id.in_(article_ids))
    else:
        # 处理有 entities 内容但尚未关联的文章
        statement = (
            select(Article)
            .where(Article.entities != "[]")
            .where(Article.entities != "")
        )

    articles = list(session.exec(statement).all())
    results: list[dict[str, Any]] = []

    for article in articles:
        article_entities = _extract_entities_from_json(article.entities)
        for entity_info in article_entities:
            name = entity_info.get("name", "")
            entity_type = entity_info.get("type", "")

            if not name or not entity_type:
                continue

            entity_type = entity_type.lower()
            if entity_type not in ENTITY_TYPES:
                entity_type = "technology"  # 默认类型

            result = _process_single_entity(
                session, name, entity_type, article.id
            )
            results.append(result)

    if results:
        session.commit()

    return results


def _extract_entities_from_json(entities_json: str) -> list[dict[str, str]]:
    """从 JSON 字符串中提取实体列表.

    支持两种格式：
    1. [{"name": "xxx", "type": "person"}, ...]
    2. ["xxx", ...]（简单字符串列表，type 默认为空）
    """
    if not entities_json:
        return []

    try:
        parsed = json.loads(entities_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, list):
        return []

    result: list[dict[str, str]] = []
    for item in parsed:
        if isinstance(item, dict):
            result.append({
                "name": item.get("name", ""),
                "type": item.get("type", ""),
            })
        elif isinstance(item, str) and item.strip():
            result.append({"name": item.strip(), "type": ""})

    return result


def _process_single_entity(
    session: Session,
    name: str,
    entity_type: str,
    article_id: int,
) -> dict[str, Any]:
    """处理单个实体：匹配已知实体或创建新实体.

    返回处理结果字典。
    """
    entity, created = get_or_create(
        session,
        Entity,
        defaults={
            "type": entity_type,
            "first_seen_at": datetime.utcnow(),
            "mention_count": 1,
            "is_new": True,
            "meta_json": "{}",
        },
        name=name,
    )

    if created:
        is_new = True
    else:
        # 已知实体：更新 mention_count，标记为非新
        is_new = False
        entity.mention_count = entity.mention_count + 1
        entity.is_new = False
        session.add(entity)

    # 创建文章-实体关联（如果不存在）
    existing_link = session.exec(
        select(ArticleEntity).where(
            ArticleEntity.article_id == article_id,
            ArticleEntity.entity_id == entity.id,
        )
    ).first()

    if existing_link is None:
        link = ArticleEntity(article_id=article_id, entity_id=entity.id)
        session.add(link)

    return {
        "entity_name": name,
        "entity_type": entity_type,
        "is_new": is_new,
        "article_id": article_id,
    }


def match_known_entities(
    session: Session,
    entity_names: list[str],
) -> dict[str, bool]:
    """将实体名称列表与 entities 表比对，区分已知/新实体.

    参数:
        session: 数据库会话
        entity_names: 实体名称列表

    返回:
        {"entity_name": is_new, ...}
    """
    result: dict[str, bool] = {}
    for name in entity_names:
        existing = session.exec(
            select(Entity).where(Entity.name == name)
        ).first()
        result[name] = existing is None
    return result


def get_entity_stats(session: Session) -> dict[str, Any]:
    """获取实体统计信息.

    返回:
        {"total": 总数, "by_type": {type: count}, "new_count": 新实体数}
    """
    all_entities = list(session.exec(select(Entity)).all())

    by_type: dict[str, int] = {}
    new_count = 0
    for entity in all_entities:
        by_type[entity.type] = by_type.get(entity.type, 0) + 1
        if entity.is_new:
            new_count += 1

    return {
        "total": len(all_entities),
        "by_type": by_type,
        "new_count": new_count,
    }
