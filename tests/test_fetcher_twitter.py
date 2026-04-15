"""测试 Twitter 采集器 — SocialData API 集成、推文标准化、过滤逻辑、水印构建."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.fetcher.twitter import TwitterFetcher, DEFAULT_SEARCH_QUERY


# ------------------------------------------------------------------
# 测试用推文数据
# ------------------------------------------------------------------

def make_tweet(
    id_str: str = "1900000000000000001",
    full_text: str = "Just published a new paper on scaling laws for LLMs. Check it out!",
    screen_name: str = "karpathy",
    name: str = "Andrej Karpathy",
    favorite_count: int = 500,
    reply_count: int = 42,
    retweet_count: int = 120,
    in_reply_to_status_id_str: str | None = None,
    retweeted_status: dict | None = None,
    urls: list[dict] | None = None,
    created_at: str = "2025-06-01T12:00:00.000000Z",
) -> dict[str, Any]:
    """创建模拟 SocialData API 推文."""
    return {
        "id_str": id_str,
        "full_text": full_text,
        "text": None,
        "tweet_created_at": created_at,
        "user": {
            "id_str": "12345",
            "name": name,
            "screen_name": screen_name,
        },
        "favorite_count": favorite_count,
        "reply_count": reply_count,
        "retweet_count": retweet_count,
        "views_count": 50000,
        "bookmark_count": 30,
        "in_reply_to_status_id_str": in_reply_to_status_id_str,
        "retweeted_status": retweeted_status,
        "quoted_status_id_str": None,
        "is_quote_status": False,
        "entities": {
            "urls": urls or [],
            "hashtags": [],
            "user_mentions": [],
        },
    }


def make_config(
    api_key: str = "test-api-key",
    accounts: list[str] | None = None,
    search_queries: list[str] | None = None,
    min_engagement: int = 100,
) -> MagicMock:
    """创建模拟 TwitterConfig."""
    cfg = MagicMock()
    cfg.api_key = api_key
    cfg.accounts = accounts or ["karpathy", "ylecun"]
    cfg.search_queries = search_queries or []
    cfg.min_engagement = min_engagement
    cfg.fetch_interval_minutes = 30
    cfg.enabled = True
    return cfg


# ------------------------------------------------------------------
# 推文标准化测试
# ------------------------------------------------------------------

class TestNormalizeTweet:
    """测试 _normalize_tweet 方法."""

    def test_basic_normalization(self):
        fetcher = TwitterFetcher(config=make_config())
        tweet = make_tweet()
        result = fetcher._normalize_tweet(tweet)

        assert result["url"] == "https://x.com/karpathy/status/1900000000000000001"
        assert result["source"] == "twitter"
        assert result["source_name"] == "@karpathy"
        assert result["author"] == "Andrej Karpathy"
        assert "scaling laws" in result["title"]
        assert "scaling laws" in result["content_raw"]
        assert result["metrics"]["platform_score"] == 500.0
        assert result["metrics"]["upvote_count"] == 500
        assert result["metrics"]["comment_count"] == 42
        assert result["published_at"] is not None

    def test_title_truncation(self):
        fetcher = TwitterFetcher(config=make_config())
        long_text = "A" * 300
        tweet = make_tweet(full_text=long_text)
        result = fetcher._normalize_tweet(tweet)

        assert len(result["title"]) == 203  # 200 + "..."
        assert result["title"].endswith("...")
        assert result["content_raw"] == long_text

    def test_external_links_appended(self):
        fetcher = TwitterFetcher(config=make_config())
        tweet = make_tweet(urls=[
            {"expanded_url": "https://arxiv.org/abs/2401.00001"},
            {"expanded_url": "https://github.com/example/repo"},
        ])
        result = fetcher._normalize_tweet(tweet)

        assert "https://arxiv.org/abs/2401.00001" in result["content_raw"]
        assert "https://github.com/example/repo" in result["content_raw"]
        assert "Links:" in result["content_raw"]

    def test_x_internal_links_excluded(self):
        fetcher = TwitterFetcher(config=make_config())
        tweet = make_tweet(urls=[
            {"expanded_url": "https://x.com/someone/status/123"},
            {"expanded_url": "https://arxiv.org/abs/2401.00001"},
        ])
        result = fetcher._normalize_tweet(tweet)

        # x.com 内部链接不应出现在 Links 中
        assert "https://x.com/someone/status/123" not in result["content_raw"]
        assert "https://arxiv.org/abs/2401.00001" in result["content_raw"]


# ------------------------------------------------------------------
# 过滤测试
# ------------------------------------------------------------------

class TestFilterTweet:
    """测试 _filter_tweet 方法."""

    def test_passes_quality_tweet(self):
        fetcher = TwitterFetcher(config=make_config(min_engagement=100))
        tweet = make_tweet(favorite_count=500)
        assert fetcher._filter_tweet(tweet) is True

    def test_filters_retweet(self):
        fetcher = TwitterFetcher(config=make_config())
        tweet = make_tweet(retweeted_status={"id_str": "123"})
        assert fetcher._filter_tweet(tweet) is False

    def test_filters_reply(self):
        fetcher = TwitterFetcher(config=make_config())
        tweet = make_tweet(in_reply_to_status_id_str="1899999999999999999")
        assert fetcher._filter_tweet(tweet) is False

    def test_filters_short_text(self):
        fetcher = TwitterFetcher(config=make_config())
        tweet = make_tweet(full_text="OK")
        assert fetcher._filter_tweet(tweet) is False

    def test_filters_low_engagement(self):
        fetcher = TwitterFetcher(config=make_config(min_engagement=100))
        tweet = make_tweet(favorite_count=50)
        assert fetcher._filter_tweet(tweet) is False

    def test_engagement_threshold_zero(self):
        fetcher = TwitterFetcher(config=make_config(min_engagement=0))
        tweet = make_tweet(favorite_count=1)
        assert fetcher._filter_tweet(tweet) is True


# ------------------------------------------------------------------
# 水印构建测试
# ------------------------------------------------------------------

class TestBuildCursor:
    """测试 _build_cursor 方法."""

    def test_returns_max_tweet_id(self):
        fetcher = TwitterFetcher(config=make_config())
        items = [
            {"url": "https://x.com/user1/status/1900000000000000001"},
            {"url": "https://x.com/user2/status/1900000000000000005"},
            {"url": "https://x.com/user3/status/1900000000000000003"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "1900000000000000005"

    def test_returns_none_on_empty(self):
        fetcher = TwitterFetcher(config=make_config())
        assert fetcher._build_cursor([]) is None

    def test_returns_none_on_no_valid_urls(self):
        fetcher = TwitterFetcher(config=make_config())
        items = [{"url": "invalid"}]
        assert fetcher._build_cursor(items) is None


# ------------------------------------------------------------------
# fetch_items 集成测试
# ------------------------------------------------------------------

class TestFetchItems:
    """测试 fetch_items 方法."""

    def test_skips_when_no_api_key(self):
        fetcher = TwitterFetcher(config=make_config(api_key=""))
        result = fetcher.fetch_items()
        assert result == []

    @patch.object(TwitterFetcher, "_fetch_account_tweets", return_value=[])
    @patch.object(TwitterFetcher, "_fetch_search_tweets", return_value=[])
    def test_calls_both_modes(self, mock_search, mock_accounts):
        fetcher = TwitterFetcher(config=make_config())
        fetcher.fetch_items()
        mock_accounts.assert_called_once()
        mock_search.assert_called_once()

    @patch.object(TwitterFetcher, "_fetch_search_tweets")
    @patch.object(TwitterFetcher, "_fetch_account_tweets")
    def test_deduplicates_by_url(self, mock_accounts, mock_search):
        mock_accounts.return_value = [
            {"url": "https://x.com/karpathy/status/100"},
            {"url": "https://x.com/karpathy/status/101"},
        ]
        mock_search.return_value = [
            {"url": "https://x.com/karpathy/status/100"},  # 重复
            {"url": "https://x.com/ylecun/status/200"},
        ]
        fetcher = TwitterFetcher(config=make_config())
        result = fetcher.fetch_items()

        urls = [item["url"] for item in result]
        assert urls == [
            "https://x.com/karpathy/status/100",
            "https://x.com/karpathy/status/101",
            "https://x.com/ylecun/status/200",
        ]


# ------------------------------------------------------------------
# 搜索查询构建测试
# ------------------------------------------------------------------

class TestSearchQueryBuilding:
    """测试搜索查询构建逻辑."""

    @patch.object(TwitterFetcher, "_get_client")
    def test_default_query_when_empty(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tweets": [], "next_cursor": ""}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client

        fetcher = TwitterFetcher(config=make_config(search_queries=[]))
        fetcher._fetch_search_tweets()

        call_args = mock_client.get.call_args
        query = call_args[1]["params"]["query"] if "params" in call_args[1] else call_args[0][1]["query"]
        assert "AI" in query
        assert "min_faves:100" in query
        assert "-is:retweet" in query

    @patch.object(TwitterFetcher, "_get_client")
    def test_custom_queries_used(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tweets": [], "next_cursor": ""}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client

        fetcher = TwitterFetcher(config=make_config(
            search_queries=["AI agents min_faves:200"]
        ))
        fetcher._fetch_search_tweets()

        call_args = mock_client.get.call_args
        query = call_args[1]["params"]["query"] if "params" in call_args[1] else call_args[0][1]["query"]
        assert query.startswith("AI agents min_faves:200")

    @patch.object(TwitterFetcher, "_get_client")
    def test_since_id_appended(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tweets": [], "next_cursor": ""}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client

        fetcher = TwitterFetcher(config=make_config())
        fetcher._fetch_search_tweets(since="1900000000000000000")

        call_args = mock_client.get.call_args
        query = call_args[1]["params"]["query"] if "params" in call_args[1] else call_args[0][1]["query"]
        assert "since_id:1900000000000000000" in query


# ------------------------------------------------------------------
# test_connection 测试
# ------------------------------------------------------------------

class TestConnection:
    """测试 test_connection 方法."""

    def test_fails_without_api_key(self):
        fetcher = TwitterFetcher(config=make_config(api_key=""))
        result = fetcher.test_connection()
        assert result["ok"] is False
        assert "api_key" in result["error"]

    @patch.object(TwitterFetcher, "_get_client")
    def test_success_on_200(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client

        fetcher = TwitterFetcher(config=make_config())
        result = fetcher.test_connection()
        assert result["ok"] is True
        assert "latency_ms" in result

    @patch.object(TwitterFetcher, "_get_client")
    def test_balance_insufficient_on_402(self, mock_get_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 402
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client

        fetcher = TwitterFetcher(config=make_config())
        result = fetcher.test_connection()
        assert result["ok"] is False
        assert "402" in result["error"] or "余额" in result["error"]
