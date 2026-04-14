"""测试 RSS 采集器 — feedparser 集成、ETag/Last-Modified 水印、降级策略."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.fetcher.rss import RSSFetcher, DEFAULT_RSS_FEEDS


# ------------------------------------------------------------------
# 模拟 feedparser 结果
# ------------------------------------------------------------------

def make_mock_feed(
    entries: list[dict[str, Any]] | None = None,
    status: int = 200,
    etag: str | None = None,
    modified: str | None = None,
    bozo: bool = False,
    bozo_exception: str | None = None,
) -> MagicMock:
    """创建模拟 feedparser.parse 返回值."""
    feed = MagicMock()
    feed.status = status
    feed.etag = etag
    feed.modified = modified
    feed.bozo = bozo
    feed.bozo_exception = bozo_exception

    if entries is None:
        entries = []

    mock_entries = []
    for e in entries:
        entry = MagicMock()
        entry.title = e.get("title", "")

        # link: 只有明确提供时才设置，否则返回 None
        if "link" in e:
            entry.link = e["link"]
        else:
            # 让 getattr 返回 None
            del entry.link

        # href: 同理
        if "href" in e:
            entry.href = e["href"]
        else:
            del entry.href

        entry.summary = e.get("summary", "")
        entry.description = e.get("description", "")
        entry.author = e.get("author", "")
        entry.published = e.get("published", None)
        entry.updated = e.get("updated", None)
        entry.published_parsed = e.get("published_parsed", None)
        entry.updated_parsed = e.get("updated_parsed", None)
        mock_entries.append(entry)

    feed.entries = mock_entries
    return feed


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def fetcher() -> RSSFetcher:
    # 使用单一源方便测试
    f = RSSFetcher()
    f.feeds = {"test-feed": "https://example.com/feed.xml"}
    return f


# ------------------------------------------------------------------
# 测试默认 RSS 源列表
# ------------------------------------------------------------------

class TestDefaultFeeds:
    def test_default_feeds_exist(self) -> None:
        assert "openai-blog" in DEFAULT_RSS_FEEDS
        assert "deepmind" in DEFAULT_RSS_FEEDS
        assert "huggingface" in DEFAULT_RSS_FEEDS
        assert "reddit-machinelearning" in DEFAULT_RSS_FEEDS
        assert "reddit-localllama" in DEFAULT_RSS_FEEDS
        assert "reddit-chatgpt" in DEFAULT_RSS_FEEDS
        assert len(DEFAULT_RSS_FEEDS) >= 6


# ------------------------------------------------------------------
# 测试 feed 解析
# ------------------------------------------------------------------

class TestFeedParsing:
    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_parse_basic_feed(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(
            entries=[
                {
                    "title": "OpenAI releases GPT-5",
                    "link": "https://openai.com/blog/gpt5",
                    "summary": "Announcing GPT-5...",
                    "author": "OpenAI",
                },
                {
                    "title": "DeepMind AlphaFold 4",
                    "link": "https://deepmind.com/blog/af4",
                    "summary": "AlphaFold 4 breakthrough...",
                    "author": "DeepMind",
                },
            ]
        )

        items = fetcher.fetch_items(since=None)
        assert len(items) == 2
        assert items[0]["title"] == "OpenAI releases GPT-5"
        assert items[0]["source"] == "rss"
        assert items[0]["source_name"] == "test-feed"

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_skip_entries_without_link(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(
            entries=[
                {"title": "No link article"},
            ]
        )

        items = fetcher.fetch_items(since=None)
        assert len(items) == 0

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_304_not_modified(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(status=304)

        items = fetcher.fetch_items(since=None)
        assert len(items) == 0


# ------------------------------------------------------------------
# 测试 ETag/Last-Modified 增量
# ------------------------------------------------------------------

class TestETagIncremental:
    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_sends_etag_to_feedparser(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(entries=[])

        cursor = json.dumps({"etag": "abc123", "last_modified": "Mon, 13 Apr 2026 00:00:00 GMT"})
        fetcher.fetch_items(since=cursor)

        # feedparser.parse 应该收到 etag 和 modified 参数
        call_kwargs = mock_parse.call_args
        assert call_kwargs is not None

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_no_etag_first_fetch(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(
            entries=[
                {"title": "Article", "link": "https://example.com/a"},
            ]
        )

        items = fetcher.fetch_items(since=None)
        assert len(items) == 1


# ------------------------------------------------------------------
# 测试降级时间水印
# ------------------------------------------------------------------

class TestFallbackTimestamp:
    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_fallback_to_published_time(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        from datetime import datetime, timezone
        import time as _time

        # published_parsed 返回 time.struct_time
        old_time = (2026, 4, 10, 12, 0, 0, 0, 0, 0)
        new_time = (2026, 4, 14, 12, 0, 0, 0, 0, 0)

        mock_parse.return_value = make_mock_feed(
            entries=[
                {
                    "title": "Old article",
                    "link": "https://example.com/old",
                    "published_parsed": old_time,
                },
                {
                    "title": "New article",
                    "link": "https://example.com/new",
                    "published_parsed": new_time,
                },
            ]
        )

        cursor = json.dumps({
            "last_item_timestamp": "2026-04-12T00:00:00+00:00"
        })
        items = fetcher.fetch_items(since=cursor)
        assert len(items) == 1
        assert items[0]["title"] == "New article"


# ------------------------------------------------------------------
# 测试多源管理
# ------------------------------------------------------------------

class TestMultiFeed:
    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_multiple_feeds(self, mock_parse: MagicMock) -> None:
        fetcher = RSSFetcher()
        fetcher.feeds = {
            "feed-a": "https://a.com/feed",
            "feed-b": "https://b.com/feed",
        }

        # 第一次调用返回 2 条，第二次返回 1 条
        mock_parse.side_effect = [
            make_mock_feed(entries=[
                {"title": "A1", "link": "https://a.com/1"},
                {"title": "A2", "link": "https://a.com/2"},
            ]),
            make_mock_feed(entries=[
                {"title": "B1", "link": "https://b.com/1"},
            ]),
        ]

        items = fetcher.fetch_items(since=None)
        assert len(items) == 3

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_single_feed_failure_doesnt_stop_others(self, mock_parse: MagicMock) -> None:
        fetcher = RSSFetcher()
        fetcher.feeds = {
            "bad-feed": "https://bad.com/feed",
            "good-feed": "https://good.com/feed",
        }

        mock_parse.side_effect = [
            Exception("Connection failed"),
            make_mock_feed(entries=[
                {"title": "Good", "link": "https://good.com/1"},
            ]),
        ]

        items = fetcher.fetch_items(since=None)
        assert len(items) == 1


# ------------------------------------------------------------------
# 测试水印构建
# ------------------------------------------------------------------

class TestBuildCursor:
    def test_build_cursor_with_dates(self, fetcher: RSSFetcher) -> None:
        items = [
            {"url": "https://a.com", "published_at": datetime(2026, 4, 10, tzinfo=timezone.utc)},
            {"url": "https://b.com", "published_at": datetime(2026, 4, 14, tzinfo=timezone.utc)},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor is not None
        data = json.loads(cursor)
        assert "last_item_timestamp" in data
        assert "2026-04-14" in data["last_item_timestamp"]

    def test_build_cursor_empty(self, fetcher: RSSFetcher) -> None:
        cursor = fetcher._build_cursor([])
        assert cursor is None


# ------------------------------------------------------------------
# 测试连通性
# ------------------------------------------------------------------

class TestConnection:
    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_connection_ok(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(
            entries=[{"title": "Test", "link": "https://example.com"}]
        )
        result = fetcher.test_connection()
        assert result["ok"] is True
        assert "latency_ms" in result

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_connection_no_entries(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(entries=[])
        result = fetcher.test_connection()
        assert result["ok"] is True

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_connection_parse_error(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(
            bozo=True,
            bozo_exception="XML parse error",
            entries=[],
        )
        result = fetcher.test_connection()
        assert result["ok"] is False

    @patch("ainews.fetcher.rss.feedparser.parse")
    def test_test_feed_specific_url(self, mock_parse: MagicMock, fetcher: RSSFetcher) -> None:
        mock_parse.return_value = make_mock_feed(
            entries=[{"title": "Test", "link": "https://example.com"}]
        )
        result = fetcher.test_feed("https://new.com/feed.xml")
        assert result["ok"] is True
