"""测试数据库：建表、CRUD、唯一约束."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ainews.storage.models import Article, Entity, FetchLog, PushLog
from ainews.storage.crud import get_or_create, upsert, bulk_insert


@pytest.fixture
def engine():
    """创建内存 SQLite 引擎."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """创建测试 Session."""
    with Session(engine) as s:
        yield s


class TestModels:
    """模型建表测试."""

    def test_create_tables(self, engine) -> None:
        """验证所有表可成功创建."""
        from ainews.storage.models import (
            Article, SourceMetric, FetchLog, Entity,
            ArticleEntity, Cluster, PushLog,
        )
        tables = SQLModel.metadata.tables
        assert "articles" in tables
        assert "source_metrics" in tables
        assert "fetch_log" in tables
        assert "entities" in tables
        assert "article_entities" in tables
        assert "clusters" in tables
        assert "push_log" in tables

    def test_insert_article(self, session: Session) -> None:
        article = Article(url="https://example.com/1", title="Test Article")
        session.add(article)
        session.commit()

        result = session.get(Article, 1)
        assert result is not None
        assert result.url == "https://example.com/1"
        assert result.title == "Test Article"
        assert result.status == "unread"
        assert result.processed is False

    def test_article_defaults(self, session: Session) -> None:
        article = Article(url="https://example.com/2")
        session.add(article)
        session.commit()

        result = session.get(Article, 1)
        assert result.trend_score == 0.0
        assert result.is_trending is False
        assert result.dingtalk_sent is False
        assert result.obsidian_synced is False

    def test_url_unique_constraint(self, session: Session) -> None:
        article1 = Article(url="https://example.com/dup", title="First")
        session.add(article1)
        session.commit()

        article2 = Article(url="https://example.com/dup", title="Second")
        session.add(article2)
        with pytest.raises(Exception):
            session.commit()

    def test_insert_entity(self, session: Session) -> None:
        entity = Entity(name="OpenAI", type="company", mention_count=1, is_new=True)
        session.add(entity)
        session.commit()

        result = session.get(Entity, 1)
        assert result.name == "OpenAI"
        assert result.type == "company"
        assert result.is_new is True

    def test_entity_name_unique(self, session: Session) -> None:
        entity1 = Entity(name="OpenAI", type="company")
        session.add(entity1)
        session.commit()

        entity2 = Entity(name="OpenAI", type="company")
        session.add(entity2)
        with pytest.raises(Exception):
            session.commit()

    def test_fetch_log(self, session: Session) -> None:
        log = FetchLog(source="hackernews", last_fetch_at=datetime.now(), items_fetched=10)
        session.add(log)
        session.commit()

        result = session.get(FetchLog, 1)
        assert result.source == "hackernews"
        assert result.items_fetched == 10

    def test_push_log(self, session: Session) -> None:
        article = Article(url="https://example.com/1", title="Test")
        session.add(article)
        session.commit()

        log = PushLog(article_id=1, push_type="feedcard", pushed_at=datetime.now())
        session.add(log)
        session.commit()

        result = session.get(PushLog, 1)
        assert result.push_type == "feedcard"


class TestCRUD:
    """CRUD 辅助函数测试."""

    def test_get_or_create_new(self, session: Session) -> None:
        entity, created = get_or_create(session, Entity, name="OpenAI", type="company")
        assert created is True
        assert entity.name == "OpenAI"
        assert entity.id is not None

    def test_get_or_create_existing(self, session: Session) -> None:
        entity, created = get_or_create(session, Entity, name="OpenAI", type="company")
        assert created is True

        entity2, created2 = get_or_create(session, Entity, name="OpenAI")
        assert created2 is False
        assert entity2.id == entity.id

    def test_upsert_create(self, session: Session) -> None:
        entity = upsert(session, Entity, {"name": "OpenAI"}, {"type": "company", "mention_count": 1})
        assert entity.name == "OpenAI"
        assert entity.mention_count == 1

    def test_upsert_update(self, session: Session) -> None:
        entity = upsert(session, Entity, {"name": "OpenAI"}, {"type": "company", "mention_count": 1})
        updated = upsert(session, Entity, {"name": "OpenAI"}, {"mention_count": 5})
        assert updated.mention_count == 5

    def test_bulk_insert(self, session: Session) -> None:
        articles = [
            Article(url=f"https://example.com/{i}", title=f"Article {i}")
            for i in range(5)
        ]
        bulk_insert(session, articles)
        session.commit()

        from sqlmodel import select
        result = session.exec(select(Article)).all()
        assert len(result) == 5
