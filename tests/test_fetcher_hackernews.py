"""测试 HackerNews 采集器 — Firebase/Algolia API、AI 关键词过滤、增量逻辑."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.fetcher.hackernews import HackerNewsFetcher, _is_ai_related


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def fetcher() -> HackerNewsFetcher:
    return HackerNewsFetcher()


# ------------------------------------------------------------------
# 测试 AI 关键词过滤
# ------------------------------------------------------------------

class TestAIKeywordFilter:
    @pytest.mark.parametrize("title", [
        "New GPT-5 model shows improved reasoning",
        "OpenAI releases new API",
        "Building RAG systems with LangChain",
        "Anthropic Claude 4 benchmarks",
        "DeepMind achieves breakthrough in protein folding",
        "Understanding Transformer architecture",
        "LLM fine-tuning best practices",
        "Agent-based AI systems are the future",
        "MCP protocol for tool integration",
        "Stable Diffusion 4.0 announced",
    ])
    def test_ai_related_titles(self, title: str) -> None:
        assert _is_ai_related(title) is True

    @pytest.mark.parametrize("title", [
        "Best hiking trails in California",
        "Rust vs Go performance comparison",
        "New JavaScript framework released",
        "How to cook pasta perfectly",
        "The best mechanical keyboards 2026",
    ])
    def test_non_ai_titles(self, title: str) -> None:
        assert _is_ai_related(title) is False

    def test_case_insensitive(self) -> None:
        assert _is_ai_related("AI is great") is True
        assert _is_ai_related("ai is great") is True


# ------------------------------------------------------------------
# 测试 Firebase API 集成
# ------------------------------------------------------------------

class TestFirebaseAPI:
    def test_fetch_items_basic(self, fetcher: HackerNewsFetcher) -> None:
        """测试基本 Firebase 采集流程."""
        topstories_resp = MagicMock()
        topstories_resp.status_code = 200
        topstories_resp.json.return_value = [1, 2, 3]

        item_1 = MagicMock()
        item_1.status_code = 200
        item_1.json.return_value = {
            "id": 1, "type": "story", "title": "New GPT model released",
            "url": "https://example.com/gpt", "score": 100,
            "descendants": 50, "time": 1712966400, "by": "user1",
        }

        item_2 = MagicMock()
        item_2.status_code = 200
        item_2.json.return_value = {
            "id": 2, "type": "story", "title": "Best hiking trails",
            "url": "https://example.com/hiking", "score": 200,
            "descendants": 10, "time": 1712966500, "by": "user2",
        }

        item_3 = MagicMock()
        item_3.status_code = 200
        item_3.json.return_value = {
            "id": 3, "type": "story", "title": "LLM reasoning breakthrough",
            "url": "https://example.com/llm", "score": 300,
            "descendants": 80, "time": 1712966600, "by": "user3",
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = [topstories_resp, item_1, item_2, item_3]
        fetcher._client = mock_client

        items = fetcher.fetch_items(since=None)

        # 只有 AI 相关的文章
        assert len(items) == 2
        assert items[0]["title"] == "New GPT model released"
        assert items[1]["title"] == "LLM reasoning breakthrough"
        assert items[0]["metrics"]["platform_score"] == 100.0

    def test_fetch_items_with_since(self, fetcher: HackerNewsFetcher) -> None:
        """测试增量过滤."""
        topstories_resp = MagicMock()
        topstories_resp.status_code = 200
        topstories_resp.json.return_value = [1, 2]

        item_1 = MagicMock()
        item_1.status_code = 200
        item_1.json.return_value = {
            "id": 1, "type": "story", "title": "Old AI news",
            "url": "https://example.com/old", "score": 50,
            "time": 1712966300, "by": "user1",
        }

        item_2 = MagicMock()
        item_2.status_code = 200
        item_2.json.return_value = {
            "id": 2, "type": "story", "title": "New AI news",
            "url": "https://example.com/new", "score": 100,
            "time": 1712966500, "by": "user2",
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = [topstories_resp, item_1, item_2]
        fetcher._client = mock_client

        # since=1712966400 应该过滤掉 item_1
        items = fetcher.fetch_items(since="1712966400")
        assert len(items) == 1
        assert items[0]["title"] == "New AI news"

    def test_skip_non_story_items(self, fetcher: HackerNewsFetcher) -> None:
        """跳过非 story 类型（如 comment, job）."""
        topstories_resp = MagicMock()
        topstories_resp.status_code = 200
        topstories_resp.json.return_value = [1]

        item_1 = MagicMock()
        item_1.status_code = 200
        item_1.json.return_value = {
            "id": 1, "type": "comment", "title": "AI comment",
            "text": "Great AI article", "time": 1712966600,
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = [topstories_resp, item_1]
        fetcher._client = mock_client

        items = fetcher.fetch_items(since=None)
        assert len(items) == 0

    def test_skip_items_without_url(self, fetcher: HackerNewsFetcher) -> None:
        """跳过没有 URL 的帖子（如 Ask HN）."""
        topstories_resp = MagicMock()
        topstories_resp.status_code = 200
        topstories_resp.json.return_value = [1]

        item_1 = MagicMock()
        item_1.status_code = 200
        item_1.json.return_value = {
            "id": 1, "type": "story", "title": "Ask HN: AI tools?",
            "url": "", "score": 50, "time": 1712966600,
        }

        mock_client = MagicMock()
        mock_client.get.side_effect = [topstories_resp, item_1]
        fetcher._client = mock_client

        items = fetcher.fetch_items(since=None)
        assert len(items) == 0


# ------------------------------------------------------------------
# 测试 Algolia API 集成
# ------------------------------------------------------------------

class TestAlgoliaAPI:
    def test_backfill_search(self, fetcher: HackerNewsFetcher) -> None:
        """测试 Algolia 回填搜索."""
        algolia_resp = MagicMock()
        algolia_resp.status_code = 200
        algolia_resp.json.return_value = {
            "hits": [
                {
                    "title": "New OpenAI model",
                    "url": "https://example.com/openai",
                    "points": 500,
                    "num_comments": 100,
                    "created_at": "2026-04-10T12:00:00Z",
                    "created_at_i": 1744286400,
                    "author": "user1",
                },
                {
                    "title": "Best restaurants in NYC",
                    "url": "https://example.com/food",
                    "points": 20,
                    "num_comments": 5,
                    "created_at": "2026-04-11T12:00:00Z",
                    "created_at_i": 1744372800,
                    "author": "user2",
                },
            ]
        }

        mock_client = MagicMock()
        mock_client.get.return_value = algolia_resp
        fetcher._client = mock_client

        items = fetcher.fetch_items(since=None, backfill_days=7)
        assert len(items) == 1
        assert items[0]["title"] == "New OpenAI model"
        assert items[0]["metrics"]["platform_score"] == 500.0

    def test_algolia_empty_results(self, fetcher: HackerNewsFetcher) -> None:
        """测试 Algolia 空结果."""
        algolia_resp = MagicMock()
        algolia_resp.status_code = 200
        algolia_resp.json.return_value = {"hits": []}

        mock_client = MagicMock()
        mock_client.get.return_value = algolia_resp
        fetcher._client = mock_client

        items = fetcher.fetch_items(since=None, backfill_days=7)
        assert len(items) == 0


# ------------------------------------------------------------------
# 测试水印构建
# ------------------------------------------------------------------

class TestBuildCursor:
    def test_build_cursor(self, fetcher: HackerNewsFetcher) -> None:
        items = [
            {"url": "https://a.com", "time": 100.0},
            {"url": "https://b.com", "time": 200.0},
            {"url": "https://c.com", "time": 150.0},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "200.0"

    def test_build_cursor_empty(self, fetcher: HackerNewsFetcher) -> None:
        cursor = fetcher._build_cursor([])
        assert cursor is None


# ------------------------------------------------------------------
# 测试连通性
# ------------------------------------------------------------------

class TestConnection:
    def test_connection_ok(self, fetcher: HackerNewsFetcher) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = list(range(500))

        mock_client = MagicMock()
        mock_client.get.return_value = resp
        fetcher._client = mock_client

        result = fetcher.test_connection()
        assert result["ok"] is True
        assert "latency_ms" in result

    def test_connection_fail(self, fetcher: HackerNewsFetcher) -> None:
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Network error")
        fetcher._client = mock_client

        result = fetcher.test_connection()
        assert result["ok"] is False
        assert "Network error" in result["error"]
