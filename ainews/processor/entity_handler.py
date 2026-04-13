"""实体入库处理：实体查找/创建、mention_count 递增、article_entities 关联."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from ainews.storage.models import ArticleEntity, Entity

logger = logging.getLogger(__name__)

# 实体类型映射：LLM 输出的键名 -> Entity.type 值
ENTITY_TYPE_MAP: dict[str, str] = {
    "people": "person",
    "companies": "company",
    "projects": "project",
    "technologies": "technology",
}


class EntityHandler:
    """实体入库处理器."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_entities(
        self, article_id: int, entities: dict[str, list[str]]
    ) -> list[Entity]:
        """处理文章实体：查找/创建实体，递增 mention_count，创建关联.

        Args:
            article_id: 文章 ID
            entities: LLM 提取的实体字典，包含 people/companies/projects/technologies 四类

        Returns:
            处理后的 Entity 列表
        """
        all_entities: list[Entity] = []

        for category, names in entities.items():
            entity_type = ENTITY_TYPE_MAP.get(category)
            if entity_type is None:
                logger.warning("未知实体类别: %s", category)
                continue

            for name in names:
                if not name or not name.strip():
                    continue
                name = name.strip()
                entity = self._upsert_single(name, entity_type)
                all_entities.append(entity)
                self._create_association(article_id, entity.id)

        self._session.flush()
        return all_entities

    def _upsert_single(self, name: str, entity_type: str) -> Entity:
        """查找或创建单个实体，已存在则递增 mention_count.

        Args:
            name: 实体名称
            entity_type: 实体类型

        Returns:
            Entity 实例
        """
        statement = select(Entity).where(Entity.name == name)
        existing = self._session.exec(statement).first()

        if existing is not None:
            existing.mention_count = existing.mention_count + 1
            self._session.add(existing)
            return existing

        new_entity = Entity(
            name=name,
            type=entity_type,
            mention_count=1,
            is_new=True,
        )
        self._session.add(new_entity)
        self._session.flush()  # flush to get the id
        return new_entity

    def _create_association(self, article_id: int, entity_id: int) -> None:
        """创建 article_entities 关联记录（幂等）.

        Args:
            article_id: 文章 ID
            entity_id: 实体 ID
        """
        statement = select(ArticleEntity).where(
            ArticleEntity.article_id == article_id,
            ArticleEntity.entity_id == entity_id,
        )
        existing = self._session.exec(statement).first()
        if existing is not None:
            return

        association = ArticleEntity(
            article_id=article_id,
            entity_id=entity_id,
        )
        self._session.add(association)
