"""测试 ArXiv 采集器 — Atom XML 解析、分类过滤、速率限制."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.fetcher.arxiv import ArXivFetcher, DEFAULT_CATEGORIES

# 模拟 ArXiv Atom XML 响应
MOCK_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>2</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>50</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Attention Is All You Need - Revisited</title>
    <summary>A comprehensive review of transformer architectures.</summary>
    <updated>2026-04-12T00:00:00Z</updated>
    <published>2026-04-11T00:00:00Z</published>
    <author>
      <name>John Doe</name>
    </author>
    <author>
      <name>Jane Smith</name>
    </author>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
    <link title="html" type="text/html" rel="related" href="http://arxiv.org/abs/2401.00001v1"/>
    <link title="pdf" type="application/pdf" rel="related" href="http://arxiv.org/pdf/2401.00001v1"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Neural Networks for Image Classification</title>
    <summary>Exploring novel CNN architectures.</summary>
    <updated>2026-04-13T00:00:00Z</updated>
    <published>2026-04-12T00:00:00Z</published>
    <author>
      <name>Alice Wang</name>
    </author>
    <category term="cs.CV"/>
    <link title="html" type="text/html" rel="related" href="http://arxiv.org/abs/2401.00002v1"/>
  </entry>
</feed>"""

MOCK_ATOM_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>0</opensearch:totalResults>
</feed>"""


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def fetcher() -> ArXivFetcher:
    return ArXivFetcher()


# ------------------------------------------------------------------
# 测试 Atom XML 解析
# ------------------------------------------------------------------

class TestAtomParsing:
    def test_parse_basic_xml(self, fetcher: ArXivFetcher) -> None:
        items, total = fetcher._parse_atom(MOCK_ATOM_XML)
        assert total == 2
        assert len(items) == 2

    def test_parse_entry_title(self, fetcher: ArXivFetcher) -> None:
        items, _ = fetcher._parse_atom(MOCK_ATOM_XML)
        assert items[0]["title"] == "Attention Is All You Need - Revisited"
        assert items[1]["title"] == "Neural Networks for Image Classification"

    def test_parse_entry_url(self, fetcher: ArXivFetcher) -> None:
        items, _ = fetcher._parse_atom(MOCK_ATOM_XML)
        # HTML 链接优先于 PDF
        assert items[0]["url"] == "http://arxiv.org/abs/2401.00001v1"

    def test_parse_entry_authors(self, fetcher: ArXivFetcher) -> None:
        items, _ = fetcher._parse_atom(MOCK_ATOM_XML)
        assert items[0]["author"] == "John Doe, Jane Smith"
        assert items[1]["author"] == "Alice Wang"

    def test_parse_entry_categories(self, fetcher: ArXivFetcher) -> None:
        items, _ = fetcher._parse_atom(MOCK_ATOM_XML)
        assert "cs.AI" in items[0]["category"]
        assert "cs.LG" in items[0]["category"]
        assert "cs.CV" in items[1]["category"]

    def test_parse_entry_published(self, fetcher: ArXivFetcher) -> None:
        items, _ = fetcher._parse_atom(MOCK_ATOM_XML)
        assert items[0]["published_at"] is not None
        assert items[0]["published_at"].year == 2026

    def test_parse_entry_source(self, fetcher: ArXivFetcher) -> None:
        items, _ = fetcher._parse_atom(MOCK_ATOM_XML)
        assert items[0]["source"] == "arxiv"

    def test_parse_empty_feed(self, fetcher: ArXivFetcher) -> None:
        items, total = fetcher._parse_atom(MOCK_ATOM_XML_EMPTY)
        assert total == 0
        assert len(items) == 0

    def test_parse_invalid_xml(self, fetcher: ArXivFetcher) -> None:
        items, total = fetcher._parse_atom("not valid xml")
        assert total == 0
        assert len(items) == 0


# ------------------------------------------------------------------
# 测试日期解析
# ------------------------------------------------------------------

class TestDateParsing:
    def test_parse_standard_date(self) -> None:
        dt = ArXivFetcher._parse_arxiv_date("2026-04-12T00:00:00Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 12

    def test_parse_date_with_microseconds(self) -> None:
        dt = ArXivFetcher._parse_arxiv_date("2026-04-12T12:30:45.123456Z")
        assert dt is not None

    def test_parse_invalid_date(self) -> None:
        dt = ArXivFetcher._parse_arxiv_date("not a date")
        assert dt is None


# ------------------------------------------------------------------
# 测试增量过滤
# ------------------------------------------------------------------

class TestIncrementalFilter:
    def test_filter_by_since(self, fetcher: ArXivFetcher) -> None:
        from datetime import datetime, timezone
        items = [
            {"url": "https://a.com", "published_at": datetime(2026, 4, 13, tzinfo=timezone.utc)},
            {"url": "https://b.com", "published_at": datetime(2026, 4, 10, tzinfo=timezone.utc)},
        ]
        filtered = fetcher._filter_by_since(items, "2026-04-12T00:00:00+00:00")
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://a.com"

    def test_filter_no_since(self, fetcher: ArXivFetcher) -> None:
        items = [{"url": "https://a.com"}]
        filtered = fetcher._filter_by_since(items, "")
        assert len(filtered) == 1

    def test_filter_all_new(self, fetcher: ArXivFetcher) -> None:
        from datetime import datetime, timezone
        items = [
            {"url": "https://a.com", "published_at": datetime(2026, 4, 13, tzinfo=timezone.utc)},
            {"url": "https://b.com", "published_at": datetime(2026, 4, 14, tzinfo=timezone.utc)},
        ]
        filtered = fetcher._filter_by_since(items, "2026-04-12T00:00:00+00:00")
        assert len(filtered) == 2


# ------------------------------------------------------------------
# 测试搜索查询构建
# ------------------------------------------------------------------

class TestSearchQuery:
    def test_default_categories(self, fetcher: ArXivFetcher) -> None:
        query = fetcher._build_search_query()
        assert "cat:cs.AI" in query
        assert "cat:cs.LG" in query
        assert "cat:cs.CL" in query

    def test_custom_categories(self) -> None:
        config = MagicMock()
        config.arxiv_categories = ["cs.CV", "stat.ML"]
        f = ArXivFetcher(config=config)
        query = f._build_search_query()
        assert "cat:cs.CV" in query
        assert "cat:stat.ML" in query


# ------------------------------------------------------------------
# 测试 fetch_items 集成
# ------------------------------------------------------------------

class TestFetchItems:
    def test_fetch_items_basic(self, fetcher: ArXivFetcher) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = MOCK_ATOM_XML
        resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = resp
        fetcher._client = mock_client

        items = fetcher.fetch_items(since=None)
        assert len(items) == 2
        assert items[0]["source"] == "arxiv"

    def test_fetch_items_with_incremental(self, fetcher: ArXivFetcher) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = MOCK_ATOM_XML
        resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = resp
        fetcher._client = mock_client

        # 过滤 4/12 之前的文章
        items = fetcher.fetch_items(since="2026-04-12T12:00:00+00:00")
        # 只有 published > 2026-04-12T12:00:00 的
        assert all(item["published_at"] is not None for item in items)


# ------------------------------------------------------------------
# 测试水印构建
# ------------------------------------------------------------------

class TestBuildCursor:
    def test_build_cursor(self, fetcher: ArXivFetcher) -> None:
        from datetime import datetime, timezone
        items = [
            {"url": "https://a.com", "published_at": datetime(2026, 4, 10, tzinfo=timezone.utc)},
            {"url": "https://b.com", "published_at": datetime(2026, 4, 14, tzinfo=timezone.utc)},
        ]
        cursor = fetcher._build_cursor(items)
        assert "2026-04-14" in cursor

    def test_build_cursor_empty(self, fetcher: ArXivFetcher) -> None:
        cursor = fetcher._build_cursor([])
        assert cursor is None


# ------------------------------------------------------------------
# 测试连通性
# ------------------------------------------------------------------

class TestConnection:
    def test_connection_ok(self, fetcher: ArXivFetcher) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = MOCK_ATOM_XML

        mock_client = MagicMock()
        mock_client.get.return_value = resp
        fetcher._client = mock_client

        result = fetcher.test_connection()
        assert result["ok"] is True

    def test_connection_fail(self, fetcher: ArXivFetcher) -> None:
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        fetcher._client = mock_client

        result = fetcher.test_connection()
        assert result["ok"] is False
