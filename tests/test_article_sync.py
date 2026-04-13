"""测试文章同步: slug 生成、REST API 写入、文件系统降级、幂等性、frontmatter 更新."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine

from ainews.publisher.article_sync import (
    sync_articles,
    update_article_frontmatter,
)
from ainews.publisher.obsidian_client import ObsidianClient
from ainews.publisher.obsidian_templates import generate_slug
from ainews.storage.models import Article


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    """创建内存数据库 session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(tmp_path: Path) -> ObsidianClient:
    """创建测试用 ObsidianClient."""
    return ObsidianClient(
        api_key="test-key",
        port=27124,
        vault_path=str(tmp_path),
    )


def _create_article(
    session: Session,
    **overrides: object,
) -> Article:
    """创建测试文章."""
    defaults = {
        "url": "https://example.com/test",
        "url_hash": "abc123",
        "title": "GPT-6 Announced: Real-Time Reasoning Breakthrough",
        "source": "hackernews",
        "source_name": "HackerNews",
        "author": "John",
        "category": "industry",
        "summary_zh": "测试摘要",
        "relevance": 9.0,
        "tags": '["AI"]',
        "entities": '[{"name": "OpenAI", "type": "company"}]',
        "trend_score": 8.5,
        "is_trending": True,
        "platforms": '["hackernews"]',
        "status": "unread",
        "processed": True,
        "dingtalk_sent": False,
        "obsidian_synced": False,
        "published_at": datetime(2026, 4, 13),
        "fetched_at": datetime(2026, 4, 13),
        "imported_at": datetime(2026, 4, 13),
        "obsidian_path": "",
    }
    defaults.update(overrides)
    article = Article(**defaults)  # type: ignore[arg-type]
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


class TestSlugGeneration:
    """slug 生成测试."""

    def test_standard_slug(self) -> None:
        assert generate_slug("Hello World") == "hello-world"

    def test_special_chars_removed(self) -> None:
        slug = generate_slug("AI's $100B Fund!")
        assert "'" not in slug
        assert "$" not in slug

    def test_truncation(self) -> None:
        slug = generate_slug("A" * 100)
        assert len(slug) <= 60


class TestSyncArticles:
    """文章同步主流程测试."""

    def test_sync_no_articles(self, db_session: Session, client: ObsidianClient) -> None:
        synced, skipped = sync_articles(db_session, client)
        assert synced == 0
        assert skipped == 0

    def test_sync_single_article_rest(
        self, db_session: Session, client: ObsidianClient
    ) -> None:
        article = _create_article(db_session)

        mock_response = httpx.Response(204, request=httpx.Request("PUT", "https://127.0.0.1:27124/v0/vault/test"))
        with patch.object(client._client, "request", return_value=mock_response):
            synced, skipped = sync_articles(db_session, client)

        assert synced == 1
        assert skipped == 0

        # 验证数据库标记
        db_session.refresh(article)
        assert article.obsidian_synced is True
        assert "AI-News/industry/" in article.obsidian_path

    def test_sync_single_article_filesystem(
        self, db_session: Session, client: ObsidianClient, tmp_path: Path
    ) -> None:
        article = _create_article(db_session)
        client._degraded = True

        synced, skipped = sync_articles(db_session, client)

        assert synced == 1
        assert skipped == 0

        # 验证文件存在
        db_session.refresh(article)
        assert article.obsidian_synced is True
        file_path = tmp_path / article.obsidian_path
        assert file_path.exists()

    def test_sync_idempotent_filesystem(
        self, db_session: Session, client: ObsidianClient, tmp_path: Path
    ) -> None:
        """文件系统模式下，已存在文件跳过但标记为成功."""
        article = _create_article(db_session)
        client._degraded = True

        # 第一次同步
        sync_articles(db_session, client)
        db_session.refresh(article)
        assert article.obsidian_synced is True

        # 创建第二篇未同步文章来验证幂等性
        _create_article(
            db_session,
            url="https://example.com/test2",
            url_hash="def456",
            title="Another Article",
            obsidian_synced=False,
        )

        # 第二次同步 - 已同步的不会被查到
        synced, _ = sync_articles(db_session, client)
        assert synced == 1  # 只同步第二篇


class TestFrontmatterUpdate:
    """frontmatter 更新测试."""

    def test_update_frontmatter_rest(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(204, request=httpx.Request("PATCH", "https://127.0.0.1:27124/v0/vault/test"))
        with patch.object(client._client, "request", return_value=mock_response):
            article = SimpleNamespace(
                obsidian_path="AI-News/industry/test.md",
                trend_score=8.7,
                is_trending=True,
                platforms='["hackernews", "reddit"]',
            )
            result = update_article_frontmatter(client, article)  # type: ignore
            assert result is True

    def test_update_frontmatter_no_path(self, client: ObsidianClient) -> None:
        article = SimpleNamespace(obsidian_path="", trend_score=8.0, is_trending=True, platforms="[]")
        result = update_article_frontmatter(client, article)  # type: ignore
        assert result is False
