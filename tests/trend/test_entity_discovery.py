"""测试实体发现引擎."""

from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, create_engine, SQLModel

from ainews.storage.models import Article, ArticleEntity, Entity
from ainews.trend.entity_discovery import (
    _extract_entities_from_json,
    discover_entities,
    get_entity_stats,
    match_known_entities,
)


def _setup_test_db() -> Session:
    """创建内存数据库用于测试."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    from sqlmodel import Session
    return Session(engine)


class TestExtractEntitiesFromJson:
    """JSON 实体提取测试."""

    def test_dict_list(self) -> None:
        data = '[{"name": "OpenAI", "type": "company"}, {"name": "GPT-5", "type": "technology"}]'
        result = _extract_entities_from_json(data)
        assert len(result) == 2
        assert result[0]["name"] == "OpenAI"
        assert result[1]["type"] == "technology"

    def test_string_list(self) -> None:
        data = '["OpenAI", "GPT-5"]'
        result = _extract_entities_from_json(data)
        assert len(result) == 2
        assert result[0]["name"] == "OpenAI"
        assert result[0]["type"] == ""

    def test_empty_string(self) -> None:
        result = _extract_entities_from_json("")
        assert result == []

    def test_invalid_json(self) -> None:
        result = _extract_entities_from_json("not json")
        assert result == []

    def test_empty_list(self) -> None:
        result = _extract_entities_from_json("[]")
        assert result == []

    def test_mixed_types(self) -> None:
        data = '[{"name": "OpenAI", "type": "company"}, "GPT-5"]'
        result = _extract_entities_from_json(data)
        assert len(result) == 2


class TestDiscoverEntities:
    """实体发现测试."""

    def test_discover_new_entity(self) -> None:
        session = _setup_test_db()
        # 创建有实体的文章
        article = Article(
            url="https://example.com/1",
            title="Test",
            entities=json.dumps([{"name": "OpenAI", "type": "company"}]),
        )
        session.add(article)
        session.commit()

        results = discover_entities(session)
        assert len(results) == 1
        assert results[0]["entity_name"] == "OpenAI"
        assert results[0]["is_new"] is True

        # 验证 entities 表
        entity = session.exec(
            __import__("sqlmodel").select(Entity).where(Entity.name == "OpenAI")
        ).first()
        assert entity is not None
        assert entity.is_new is True
        assert entity.mention_count == 1

        session.close()

    def test_known_entity_update(self) -> None:
        session = _setup_test_db()
        # 先创建已知实体
        entity = Entity(
            name="OpenAI",
            type="company",
            mention_count=5,
            is_new=False,
            first_seen_at=datetime.utcnow(),
        )
        session.add(entity)
        session.commit()

        # 创建文章引用该实体
        article = Article(
            url="https://example.com/2",
            title="Test",
            entities=json.dumps([{"name": "OpenAI", "type": "company"}]),
        )
        session.add(article)
        session.commit()

        results = discover_entities(session)
        assert len(results) == 1
        assert results[0]["is_new"] is False

        # 验证 mention_count 递增
        session.refresh(entity)
        assert entity.mention_count == 6

        session.close()

    def test_multiple_entities(self) -> None:
        session = _setup_test_db()
        article = Article(
            url="https://example.com/3",
            title="Test",
            entities=json.dumps([
                {"name": "GPT-5", "type": "technology"},
                {"name": "Sam Altman", "type": "person"},
            ]),
        )
        session.add(article)
        session.commit()

        results = discover_entities(session)
        assert len(results) == 2

        session.close()


class TestMatchKnownEntities:
    """已知实体匹配测试."""

    def test_known_entity(self) -> None:
        session = _setup_test_db()
        entity = Entity(name="OpenAI", type="company")
        session.add(entity)
        session.commit()

        result = match_known_entities(session, ["OpenAI", "Unknown"])
        assert result["OpenAI"] is False
        assert result["Unknown"] is True

        session.close()

    def test_empty_list(self) -> None:
        session = _setup_test_db()
        result = match_known_entities(session, [])
        assert result == {}
        session.close()


class TestGetEntityStats:
    """实体统计测试."""

    def test_empty_db(self) -> None:
        session = _setup_test_db()
        stats = get_entity_stats(session)
        assert stats["total"] == 0
        assert stats["new_count"] == 0
        session.close()

    def test_with_entities(self) -> None:
        session = _setup_test_db()
        session.add(Entity(name="A", type="person", is_new=True))
        session.add(Entity(name="B", type="company", is_new=False))
        session.add(Entity(name="C", type="person", is_new=True))
        session.commit()

        stats = get_entity_stats(session)
        assert stats["total"] == 3
        assert stats["new_count"] == 2
        assert stats["by_type"]["person"] == 2
        assert stats["by_type"]["company"] == 1

        session.close()
