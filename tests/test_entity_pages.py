"""测试实体页面: 创建/更新、文件名规范化、重复检查."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine

from ainews.publisher.entity_pages import (
    sync_entity_pages,
    _update_entity_frontmatter,
)
from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import normalize_entity_name
from ainews.storage.models import Article, ArticleEntity, Entity


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(tmp_path: Path) -> ObsidianClient:
    return ObsidianClient(
        api_key="test-key",
        port=27124,
        vault_path=str(tmp_path),
    )


def _create_entity(
    session: Session,
    name: str = "Sam Altman",
    entity_type: str = "person",
    mention_count: int = 5,
) -> Entity:
    entity = Entity(
        name=name,
        type=entity_type,
        first_seen_at=datetime(2026, 4, 1),
        mention_count=mention_count,
        meta_json='{"company": "OpenAI"}',
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


def _create_article(session: Session, entity: Entity) -> Article:
    article = Article(
        url="https://example.com/test",
        url_hash="abc",
        title="Test Article",
        source="hackernews",
        category="industry",
        published_at=datetime(2026, 4, 13),
        fetched_at=datetime(2026, 4, 13),
        imported_at=datetime(2026, 4, 13),
    )
    session.add(article)
    session.flush()

    ae = ArticleEntity(article_id=article.id, entity_id=entity.id)
    session.add(ae)
    session.commit()
    return article


class TestEntityNameNormalization:
    """实体名称规范化测试."""

    def test_person_name(self) -> None:
        assert normalize_entity_name("Sam Altman") == "Sam-Altman"

    def test_with_parentheses(self) -> None:
        assert normalize_entity_name("AlphaGo (DeepMind)") == "AlphaGo-DeepMind"

    def test_simple_name(self) -> None:
        assert normalize_entity_name("OpenAI") == "OpenAI"

    def test_hyphenated_name(self) -> None:
        assert normalize_entity_name("GPT-6") == "GPT-6"


class TestSyncEntityPages:
    """实体页面同步测试."""

    def test_sync_no_entities(self, db_session: Session, client: ObsidianClient) -> None:
        created, updated = sync_entity_pages(db_session, client)
        assert created == 0
        assert updated == 0

    def test_sync_creates_entity_page_filesystem(
        self, db_session: Session, client: ObsidianClient, tmp_path: Path
    ) -> None:
        entity = _create_entity(db_session)
        _create_article(db_session, entity)
        client._degraded = True

        created, updated = sync_entity_pages(db_session, client)
        assert created == 1
        assert updated == 0

        # 验证文件
        file_path = tmp_path / "AI-News" / "Entities" / "People" / "Sam-Altman.md"
        assert file_path.exists()
        content = file_path.read_text()
        assert "Sam Altman" in content
        assert "person" in content

    def test_sync_updates_existing_entity_filesystem(
        self, db_session: Session, client: ObsidianClient, tmp_path: Path
    ) -> None:
        entity = _create_entity(db_session, mention_count=5)
        _create_article(db_session, entity)
        client._degraded = True

        # 第一次创建
        sync_entity_pages(db_session, client)

        # 更新 mention_count
        entity.mention_count = 10
        db_session.add(entity)
        db_session.commit()

        # 第二次更新
        created, updated = sync_entity_pages(db_session, client)
        assert updated == 1

        file_path = tmp_path / "AI-News" / "Entities" / "People" / "Sam-Altman.md"
        content = file_path.read_text()
        assert "mention_count: 10" in content

    def test_sync_creates_entity_page_rest(
        self, db_session: Session, client: ObsidianClient
    ) -> None:
        entity = _create_entity(db_session, name="Dario Amodei")
        _create_article(db_session, entity)

        # 搜索返回空 -> 创建
        search_response = httpx.Response(
            200, json=[], request=httpx.Request("POST", "https://127.0.0.1:27124/v0/search/simple/")
        )
        put_response = httpx.Response(
            204, request=httpx.Request("PUT", "https://127.0.0.1:27124/v0/vault/test")
        )

        call_count = 0

        def mock_request(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return search_response
            return put_response

        with patch.object(client._client, "request", side_effect=mock_request):
            created, updated = sync_entity_pages(db_session, client)

        assert created == 1

    def test_skip_technology_type(
        self, db_session: Session, client: ObsidianClient
    ) -> None:
        _create_entity(db_session, name="Transformers", entity_type="technology")
        created, updated = sync_entity_pages(db_session, client)
        assert created == 0
        assert updated == 0


class TestUpdateEntityFrontmatter:
    """实体 frontmatter 更新测试."""

    def test_update_mention_count(self) -> None:
        entity = SimpleNamespace(
            mention_count=15,
            first_seen_at=datetime(2026, 4, 1),
        )
        content = "---\ntype: person\nmention_count: 10\nfirst_seen: '2026-04-01'\n---\n\n# Test\n"
        result = _update_entity_frontmatter(content, entity, [])
        assert "mention_count: 15" in result

    def test_update_preserves_body(self) -> None:
        entity = SimpleNamespace(
            mention_count=5,
            first_seen_at=datetime(2026, 4, 1),
        )
        content = "---\ntype: person\nmention_count: 3\n---\n\n# Test Body\nSome content\n"
        result = _update_entity_frontmatter(content, entity, [])
        assert "# Test Body" in result
        assert "Some content" in result
