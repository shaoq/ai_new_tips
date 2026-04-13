"""测试 BaseFetcher — 水印读写、URL 去重、批量入库."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from ainews.fetcher.base import BaseFetcher
from ainews.storage.models import Article, FetchLog


# ------------------------------------------------------------------
# 测试用 BaseFetcher 子类
# ------------------------------------------------------------------

class DummyFetcher(BaseFetcher):
    """测试用简单采集器."""

    def __init__(self) -> None:
        super().__init__(source_name="test_source")
        self._items: list[dict[str, Any]] = []

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return self._items

    def test_connection(self) -> dict[str, Any]:
        return {"ok": True, "latency_ms": 10, "detail": "test ok"}


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    """创建内存数据库引擎."""
    eng = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """创建测试 Session."""
    with Session(engine, expire_on_commit=False) as sess:
        yield sess


@pytest.fixture
def fetcher():
    return DummyFetcher()


# ------------------------------------------------------------------
# 测试 URL 去重
# ------------------------------------------------------------------

class TestDedupByUrl:
    def test_empty_list(self, fetcher: DummyFetcher) -> None:
        result = fetcher._dedup_by_url([])
        assert result == []

    def test_no_duplicates(self, fetcher: DummyFetcher, session: Session) -> None:
        items = [
            {"url": "https://example.com/1", "title": "A"},
            {"url": "https://example.com/2", "title": "B"},
        ]
        with patch.object(fetcher, "_get_session", return_value=session):
            with patch("ainews.storage.database.get_engine", return_value=session.get_bind()):
                result = fetcher._dedup_by_url(items)
        assert len(result) == 2

    def test_with_existing_urls(self, fetcher: DummyFetcher, session: Session) -> None:
        url = "https://example.com/existing"
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        existing = Article(url=url, url_hash=url_hash, title="existing")
        session.add(existing)
        session.commit()

        items = [
            {"url": url, "title": "duplicate"},
            {"url": "https://example.com/new", "title": "new"},
        ]
        with patch.object(fetcher, "_get_session", return_value=session):
            result = fetcher._dedup_by_url(items)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/new"

    def test_all_duplicates(self, fetcher: DummyFetcher, session: Session) -> None:
        url = "https://example.com/dup"
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        session.add(Article(url=url, url_hash=url_hash))
        session.commit()

        items = [{"url": url, "title": "dup"}]
        with patch.object(fetcher, "_get_session", return_value=session):
            result = fetcher._dedup_by_url(items)
        assert result == []


# ------------------------------------------------------------------
# 测试水印读写
# ------------------------------------------------------------------

class TestCursorManagement:
    def test_load_cursor_no_record(self, fetcher: DummyFetcher, session: Session) -> None:
        with patch.object(fetcher, "_get_session", return_value=session):
            cursor = fetcher._load_cursor()
        assert cursor is None

    def test_load_cursor_with_record(self, fetcher: DummyFetcher, session: Session) -> None:
        now = datetime.now()
        log = FetchLog(
            source="test_source",
            cursor="12345",
            last_fetch_at=now,
            items_fetched=10,
        )
        session.add(log)
        session.commit()

        with patch.object(fetcher, "_get_session", return_value=session):
            cursor = fetcher._load_cursor()
        assert cursor == "12345"

    def test_update_cursor_creates_new(self, fetcher: DummyFetcher, session: Session) -> None:
        with patch.object(fetcher, "_get_session", return_value=session):
            fetcher._update_cursor("new_cursor", 5)

        log = session.exec(
            select(FetchLog).where(FetchLog.source == "test_source")
        ).first()
        assert log is not None
        assert log.cursor == "new_cursor"
        assert log.items_fetched == 5

    def test_update_cursor_updates_existing(self, fetcher: DummyFetcher, session: Session) -> None:
        log = FetchLog(source="test_source", cursor="old", items_fetched=0)
        session.add(log)
        session.commit()

        with patch.object(fetcher, "_get_session", return_value=session):
            fetcher._update_cursor("new_cursor", 10)

        log = session.exec(
            select(FetchLog).where(FetchLog.source == "test_source")
        ).first()
        assert log is not None
        assert log.cursor == "new_cursor"
        assert log.items_fetched == 10


# ------------------------------------------------------------------
# 测试批量入库
# ------------------------------------------------------------------

class TestSaveArticles:
    def test_save_empty_list(self, fetcher: DummyFetcher, session: Session) -> None:
        with patch.object(fetcher, "_get_session", return_value=session):
            articles = fetcher._save_articles([])
        assert articles == []

    def test_save_articles(self, fetcher: DummyFetcher, session: Session) -> None:
        now = datetime.now(tz=timezone.utc)
        items = [
            {
                "url": "https://example.com/1",
                "title": "Article 1",
                "content_raw": "Content 1",
                "source": "test_source",
                "source_name": "Test",
                "author": "Author",
                "published_at": now,
            },
            {
                "url": "https://example.com/2",
                "title": "Article 2",
                "content_raw": "Content 2",
                "source": "test_source",
                "source_name": "Test",
                "author": "",
                "published_at": None,
            },
        ]

        with patch.object(fetcher, "_get_session", return_value=session):
            articles = fetcher._save_articles(items)

        assert len(articles) == 2
        assert articles[0].title == "Article 1"
        assert articles[0].status == "unread"
        assert articles[0].processed is False
        assert articles[0].url_hash != ""

        # 验证数据库记录
        db_articles = session.exec(select(Article)).all()
        assert len(db_articles) == 2

    def test_save_with_metrics(self, fetcher: DummyFetcher, session: Session) -> None:
        from ainews.storage.models import SourceMetric

        items = [
            {
                "url": "https://example.com/metrics",
                "title": "With Metrics",
                "metrics": {
                    "platform_score": 100.0,
                    "comment_count": 50,
                    "upvote_count": 200,
                },
            },
        ]

        with patch.object(fetcher, "_get_session", return_value=session):
            articles = fetcher._save_articles(items)

        assert len(articles) == 1
        metrics = session.exec(select(SourceMetric)).all()
        assert len(metrics) == 1
        assert metrics[0].platform_score == 100.0
        assert metrics[0].comment_count == 50


# ------------------------------------------------------------------
# 测试 URL 哈希
# ------------------------------------------------------------------

class TestUrlHash:
    def test_consistent_hash(self) -> None:
        url = "https://example.com/test"
        h1 = BaseFetcher._url_hash(url)
        h2 = BaseFetcher._url_hash(url)
        assert h1 == h2
        assert h1 == hashlib.sha256(url.encode()).hexdigest()

    def test_different_urls_different_hashes(self) -> None:
        h1 = BaseFetcher._url_hash("https://a.com")
        h2 = BaseFetcher._url_hash("https://b.com")
        assert h1 != h2


# ------------------------------------------------------------------
# 测试 fetch 完整流程
# ------------------------------------------------------------------

class TestFetchFlow:
    def test_fetch_dry_run(self, fetcher: DummyFetcher, session: Session) -> None:
        fetcher.set_items([
            {"url": "https://example.com/1", "title": "A"},
        ])
        with patch.object(fetcher, "_get_session", return_value=session):
            articles = fetcher.fetch(dry_run=True)
        assert articles == []

    def test_fetch_force_ignores_cursor(self, fetcher: DummyFetcher, session: Session) -> None:
        # 设置已有水印
        log = FetchLog(source="test_source", cursor="old_cursor")
        session.add(log)
        session.commit()

        fetcher.set_items([
            {"url": "https://example.com/1", "title": "A"},
        ])

        # force=True 应该忽略水印，since=None
        with patch.object(fetcher, "_get_session", return_value=session):
            articles = fetcher.fetch(force=True)
        assert len(articles) == 1

    def test_fetch_no_items(self, fetcher: DummyFetcher, session: Session) -> None:
        fetcher.set_items([])
        with patch.object(fetcher, "_get_session", return_value=session):
            articles = fetcher.fetch()
        assert articles == []
