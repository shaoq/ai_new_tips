"""实体入库测试."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from ainews.processor.entity_handler import EntityHandler
from ainews.storage.models import Article, ArticleEntity, Entity


@pytest.fixture
def engine():
    """创建内存数据库引擎."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """创建数据库 session."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def handler(session: Session) -> EntityHandler:
    """创建 EntityHandler."""
    return EntityHandler(session)


def _make_article(**overrides: object) -> Article:
    defaults = {
        "url": "https://example.com/test",
        "title": "Test Article",
        "content_raw": "Content",
    }
    defaults.update(overrides)
    return Article(**defaults)  # type: ignore[arg-type]


class TestUpsertEntities:
    """upsert_entities 测试."""

    def test_create_new_entities(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        entities = {
            "people": ["Sam Altman"],
            "companies": ["OpenAI"],
            "projects": ["GPT-5"],
            "technologies": ["llm"],
        }

        result = handler.upsert_entities(article.id, entities)

        assert len(result) == 4

        # Verify entities in DB
        all_entities = session.exec(select(Entity)).all()
        assert len(all_entities) == 4
        names = {e.name for e in all_entities}
        assert names == {"Sam Altman", "OpenAI", "GPT-5", "llm"}

    def test_new_entity_has_correct_type(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        handler.upsert_entities(article.id, {
            "people": ["Alice"],
            "companies": ["Acme Corp"],
        })

        alice = session.exec(
            select(Entity).where(Entity.name == "Alice")
        ).one()
        assert alice.type == "person"

        acme = session.exec(
            select(Entity).where(Entity.name == "Acme Corp")
        ).one()
        assert acme.type == "company"

    def test_new_entity_mention_count_and_is_new(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        handler.upsert_entities(article.id, {"companies": ["OpenAI"]})

        entity = session.exec(
            select(Entity).where(Entity.name == "OpenAI")
        ).one()
        assert entity.mention_count == 1
        assert entity.is_new is True

    def test_existing_entity_increments_mention_count(
        self, handler: EntityHandler, session: Session
    ) -> None:
        # Create first article with OpenAI entity
        article1 = _make_article()
        session.add(article1)
        session.commit()
        session.refresh(article1)

        handler.upsert_entities(article1.id, {"companies": ["OpenAI"]})
        session.commit()

        # Create second article with same entity
        article2 = _make_article(url="https://example.com/test2")
        session.add(article2)
        session.commit()
        session.refresh(article2)

        handler.upsert_entities(article2.id, {"companies": ["OpenAI"]})
        session.commit()

        entity = session.exec(
            select(Entity).where(Entity.name == "OpenAI")
        ).one()
        assert entity.mention_count == 2

    def test_existing_entity_is_new_remains_false(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article1 = _make_article()
        session.add(article1)
        session.commit()
        session.refresh(article1)

        handler.upsert_entities(article1.id, {"companies": ["OpenAI"]})
        session.commit()

        # Reset is_new to False (simulating some external update)
        entity = session.exec(
            select(Entity).where(Entity.name == "OpenAI")
        ).one()
        entity.is_new = False
        session.add(entity)
        session.commit()

        article2 = _make_article(url="https://example.com/test2")
        session.add(article2)
        session.commit()
        session.refresh(article2)

        handler.upsert_entities(article2.id, {"companies": ["OpenAI"]})
        session.commit()

        entity = session.exec(
            select(Entity).where(Entity.name == "OpenAI")
        ).one()
        assert entity.is_new is False

    def test_article_entities_association_created(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        handler.upsert_entities(article.id, {
            "companies": ["OpenAI"],
            "technologies": ["llm"],
        })
        session.commit()

        associations = session.exec(
            select(ArticleEntity).where(ArticleEntity.article_id == article.id)
        ).all()
        assert len(associations) == 2

        entity_ids = {a.entity_id for a in associations}
        entities = session.exec(select(Entity)).all()
        expected_ids = {e.id for e in entities}
        assert entity_ids == expected_ids

    def test_association_idempotent(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        # First call
        handler.upsert_entities(article.id, {"companies": ["OpenAI"]})
        session.commit()

        # Second call with same entity - mention_count increments but association is not duplicated
        handler.upsert_entities(article.id, {"companies": ["OpenAI"]})
        session.commit()

        associations = session.exec(
            select(ArticleEntity).where(ArticleEntity.article_id == article.id)
        ).all()
        assert len(associations) == 1  # Association already exists, not duplicated

        entity = session.exec(
            select(Entity).where(Entity.name == "OpenAI")
        ).one()
        assert entity.mention_count == 2  # But mention count incremented

    def test_empty_entity_lists(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = handler.upsert_entities(article.id, {
            "people": [],
            "companies": [],
            "projects": [],
            "technologies": [],
        })

        assert result == []

    def test_skip_empty_entity_names(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = handler.upsert_entities(article.id, {
            "people": ["", "  ", "Alice"],
        })

        assert len(result) == 1
        assert result[0].name == "Alice"

    def test_unknown_entity_category_skipped(
        self, handler: EntityHandler, session: Session
    ) -> None:
        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = handler.upsert_entities(article.id, {
            "unknown_category": ["Something"],
        })

        assert result == []

    def test_multiple_articles_same_entity(
        self, handler: EntityHandler, session: Session
    ) -> None:
        """Two articles both mentioning OpenAI -> single Entity, count=2, two associations."""
        article1 = _make_article()
        article2 = _make_article(url="https://example.com/test2")
        session.add(article1)
        session.add(article2)
        session.commit()
        session.refresh(article1)
        session.refresh(article2)

        handler.upsert_entities(article1.id, {"companies": ["OpenAI"]})
        handler.upsert_entities(article2.id, {"companies": ["OpenAI"]})
        session.commit()

        # One entity record
        entities = session.exec(select(Entity)).all()
        assert len(entities) == 1
        assert entities[0].mention_count == 2

        # Two association records
        associations = session.exec(select(ArticleEntity)).all()
        assert len(associations) == 2
