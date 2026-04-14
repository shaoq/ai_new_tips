"""测试 Reddit 采集器 — PRAW OAuth2、AI 关键词过滤、增量逻辑、错误处理."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ainews.config.settings import RedditConfig
from ainews.fetcher.reddit import RedditFetcher, _is_ai_related


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_submission(
    *,
    id: str = "abc123",
    title: str = "New GPT model released",
    url: str = "https://example.com/gpt",
    selftext: str = "",
    author: str = "test_user",
    created_utc: float = 1712966400.0,
    score: int = 100,
    num_comments: int = 50,
    stickied: bool = False,
    permalink: str = "/r/MachineLearning/comments/abc123/new_gpt_model_released/",
) -> MagicMock:
    """创建一个模拟 PRAW Submission 的 MagicMock 对象."""
    sub = MagicMock()
    sub.id = id
    sub.title = title
    sub.url = url
    sub.selftext = selftext
    sub.author = author
    sub.created_utc = created_utc
    sub.score = score
    sub.num_comments = num_comments
    sub.stickied = stickied
    sub.permalink = permalink
    return sub


def _make_config(
    *,
    client_id: str = "fake_id",
    client_secret: str = "fake_secret",
    subreddits: list[str] | None = None,
) -> RedditConfig:
    """创建测试用 RedditConfig."""
    return RedditConfig(
        client_id=client_id,
        client_secret=client_secret,
        subreddits=subreddits or ["MachineLearning"],
    )


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def fetcher() -> RedditFetcher:
    """创建一个注入测试配置的 RedditFetcher."""
    config = _make_config(subreddits=["MachineLearning", "LocalLLaMA"])
    return RedditFetcher(config=config)


@pytest.fixture
def fetcher_single_sub() -> RedditFetcher:
    """创建单 subreddit 的 RedditFetcher."""
    config = _make_config(subreddits=["MachineLearning"])
    return RedditFetcher(config=config)


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
        "ChatGPT can now browse the web",
        "Meta releases Llama 4",
        "Mistral 7B open source model",
        "Multimodal reasoning with Gemini",
        "Grok 2.0 now available",
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
        assert _is_ai_related("OpenAI Is Amazing") is True

    def test_partial_word_no_match(self) -> None:
        """关键词需要全词匹配，不应匹配部分单词."""
        assert _is_ai_related("Waiting for the train") is False
        assert _is_ai_related("Captain America review") is False


# ------------------------------------------------------------------
# 测试 _normalize
# ------------------------------------------------------------------

class TestNormalize:
    def test_basic_normalization(self, fetcher: RedditFetcher) -> None:
        """测试基本字段映射."""
        submission = _make_submission()
        result = fetcher._normalize(submission, "MachineLearning")

        assert result["url"] == "https://example.com/gpt"
        assert result["title"] == "New GPT model released"
        assert result["content_raw"] == ""
        assert result["source"] == "reddit"
        assert result["source_name"] == "r/MachineLearning"
        assert result["author"] == "test_user"
        assert isinstance(result["published_at"], datetime)
        assert result["time"] == 1712966400.0
        assert result["metrics"]["platform_score"] == 100.0
        assert result["metrics"]["comment_count"] == 50

    def test_reddit_self_post_url(self, fetcher: RedditFetcher) -> None:
        """Reddit 自身链接使用 permalink 替代."""
        submission = _make_submission(
            url="https://www.reddit.com/r/MachineLearning/comments/abc123/",
            permalink="/r/MachineLearning/comments/abc123/title/",
        )
        result = fetcher._normalize(submission, "MachineLearning")

        assert result["url"] == "https://www.reddit.com/r/MachineLearning/comments/abc123/title/"

    def test_external_url_preserved(self, fetcher: RedditFetcher) -> None:
        """外部 URL 保持不变."""
        submission = _make_submission(url="https://arxiv.org/abs/2401.00001")
        result = fetcher._normalize(submission, "MachineLearning")

        assert result["url"] == "https://arxiv.org/abs/2401.00001"

    def test_deleted_author(self, fetcher: RedditFetcher) -> None:
        """已删除用户显示为 [deleted]."""
        submission = _make_submission(author=None)
        result = fetcher._normalize(submission, "MachineLearning")

        assert result["author"] == "[deleted]"

    def test_selftext_content(self, fetcher: RedditFetcher) -> None:
        """selftext 映射到 content_raw."""
        submission = _make_submission(selftext="This is a detailed AI analysis post.")
        result = fetcher._normalize(submission, "MachineLearning")

        assert result["content_raw"] == "This is a detailed AI analysis post."

    def test_empty_selftext(self, fetcher: RedditFetcher) -> None:
        """空 selftext 映射为空字符串."""
        submission = _make_submission(selftext=None)
        result = fetcher._normalize(submission, "MachineLearning")

        assert result["content_raw"] == ""


# ------------------------------------------------------------------
# 测试 fetch_items
# ------------------------------------------------------------------

class TestFetchItems:
    def test_fetch_items_basic(self, fetcher_single_sub: RedditFetcher) -> None:
        """测试基本采集流程 — hot + new 帖子."""
        ai_submission = _make_submission(
            id="ai1", title="New LLM model released", score=500,
        )
        non_ai_submission = _make_submission(
            id="non1", title="Best hiking trails", score=200,
        )
        stickied_submission = _make_submission(
            id="sticky1", title="Weekly AI thread", stickied=True,
        )

        mock_subreddit = MagicMock()
        mock_subreddit.hot.return_value = [ai_submission, non_ai_submission, stickied_submission]
        mock_subreddit.new.return_value = []

        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                items = fetcher_single_sub.fetch_items(since=None)

        # 只有 AI 相关且非置顶的帖子
        assert len(items) == 1
        assert items[0]["title"] == "New LLM model released"
        assert items[0]["metrics"]["platform_score"] == 500.0

    def test_fetch_items_dedup_across_hot_and_new(self, fetcher_single_sub: RedditFetcher) -> None:
        """测试 hot 和 new 之间去重."""
        submission = _make_submission(id="dup1", title="AI breakthrough")

        mock_subreddit = MagicMock()
        mock_subreddit.hot.return_value = [submission]
        mock_subreddit.new.return_value = [submission]  # 同一条重复出现

        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                items = fetcher_single_sub.fetch_items(since=None)

        assert len(items) == 1

    def test_fetch_items_with_since(self, fetcher_single_sub: RedditFetcher) -> None:
        """测试增量过滤 — since 参数跳过旧帖子."""
        old_submission = _make_submission(
            id="old1", title="Old AI news", created_utc=1712966300.0,
        )
        new_submission = _make_submission(
            id="new1", title="New AI news", created_utc=1712966500.0,
        )

        mock_subreddit = MagicMock()
        mock_subreddit.hot.return_value = [old_submission, new_submission]
        mock_subreddit.new.return_value = []

        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                # since=1712966400 应该过滤掉 old_submission
                items = fetcher_single_sub.fetch_items(since="1712966400")

        assert len(items) == 1
        assert items[0]["title"] == "New AI news"

    def test_fetch_items_multiple_subreddits(self, fetcher: RedditFetcher) -> None:
        """测试多 subreddit 采集."""
        sub1_ai = _make_submission(id="s1_ai", title="AI model v2")
        sub2_ai = _make_submission(id="s2_ai", title="LLM training tips")

        ml_subreddit = MagicMock()
        ml_subreddit.hot.return_value = [sub1_ai]
        ml_subreddit.new.return_value = []

        llamah_subreddit = MagicMock()
        llamah_subreddit.hot.return_value = [sub2_ai]
        llamah_subreddit.new.return_value = []

        mock_reddit = MagicMock()
        mock_reddit.subreddit.side_effect = lambda name: {
            "MachineLearning": ml_subreddit,
            "LocalLLaMA": llamah_subreddit,
        }[name]

        with patch.object(fetcher, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                items = fetcher.fetch_items(since=None)

        assert len(items) == 2
        assert items[0]["source_name"] == "r/MachineLearning"
        assert items[1]["source_name"] == "r/LocalLLaMA"

    def test_fetch_items_all_filtered(self, fetcher_single_sub: RedditFetcher) -> None:
        """所有帖子都不是 AI 相关时返回空列表."""
        non_ai = _make_submission(id="non1", title="Rust vs Go comparison")

        mock_subreddit = MagicMock()
        mock_subreddit.hot.return_value = [non_ai]
        mock_subreddit.new.return_value = []

        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                items = fetcher_single_sub.fetch_items(since=None)

        assert len(items) == 0


# ------------------------------------------------------------------
# 测试水印构建
# ------------------------------------------------------------------

class TestBuildCursor:
    def test_build_cursor_returns_max_timestamp(self, fetcher: RedditFetcher) -> None:
        items = [
            {"url": "https://a.com", "time": 100.0},
            {"url": "https://b.com", "time": 200.0},
            {"url": "https://c.com", "time": 150.0},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "200.0"

    def test_build_cursor_single_item(self, fetcher: RedditFetcher) -> None:
        items = [{"url": "https://a.com", "time": 42.5}]
        cursor = fetcher._build_cursor(items)
        assert cursor == "42.5"

    def test_build_cursor_empty(self, fetcher: RedditFetcher) -> None:
        cursor = fetcher._build_cursor([])
        assert cursor is None


# ------------------------------------------------------------------
# 测试错误处理
# ------------------------------------------------------------------

class TestErrorHandling:
    def test_oauth2_missing_credentials_raises_valueerror(self) -> None:
        """未配置 OAuth2 凭证时抛出 ValueError."""
        config = _make_config(client_id="", client_secret="")
        fetcher = RedditFetcher(config=config)

        with pytest.raises(ValueError, match="OAuth2.*凭证未配置"):
            fetcher.fetch_items()

    def test_oauth2_invalid_credentials_raises_valueerror(
        self, fetcher_single_sub: RedditFetcher,
    ) -> None:
        """OAuth2 凭证无效（401）时抛出 ValueError."""
        import prawcore

        mock_response = MagicMock()
        mock_response.status_code = 401

        error = prawcore.exceptions.ResponseException(mock_response)

        mock_subreddit = MagicMock()
        mock_subreddit.hot.side_effect = error

        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                with pytest.raises(ValueError, match="OAuth2.*凭证无效"):
                    fetcher_single_sub.fetch_items()

    def test_network_error_caught_gracefully(
        self, fetcher_single_sub: RedditFetcher,
    ) -> None:
        """网络错误被捕获，不抛异常，返回空列表."""
        import prawcore

        mock_reddit = MagicMock()
        mock_reddit.subreddit.side_effect = prawcore.exceptions.RequestException(
            original_exception=Exception("Connection reset"),
            request_args=(),
            request_kwargs={},
        )

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                items = fetcher_single_sub.fetch_items(since=None)

        # 网络错误应该被优雅地捕获，返回空列表
        assert items == []

    def test_http_error_non_401_caught_gracefully(
        self, fetcher_single_sub: RedditFetcher,
    ) -> None:
        """非 401 的 HTTP 错误被捕获，不抛异常."""
        import prawcore

        mock_response = MagicMock()
        mock_response.status_code = 503

        error = prawcore.exceptions.ResponseException(mock_response)

        mock_reddit = MagicMock()
        mock_reddit.subreddit.side_effect = error

        with patch.object(fetcher_single_sub, "_get_reddit", return_value=mock_reddit):
            with patch("ainews.fetcher.reddit.time.sleep"):
                # 503 不应该抛出异常
                items = fetcher_single_sub.fetch_items(since=None)

        assert items == []


# ------------------------------------------------------------------
# 测试连通性
# ------------------------------------------------------------------

class TestConnection:
    def test_connection_ok(self, fetcher: RedditFetcher) -> None:
        mock_reddit = MagicMock()
        mock_reddit.user.me.return_value = MagicMock(name="test_bot")

        with patch.object(fetcher, "_get_reddit", return_value=mock_reddit):
            result = fetcher.test_connection()

        assert result["ok"] is True
        assert "latency_ms" in result
        assert result["detail"] == "Reddit API 认证成功"

    def test_connection_oauth2_invalid(self, fetcher: RedditFetcher) -> None:
        import prawcore

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_reddit = MagicMock()
        mock_reddit.user.me.side_effect = prawcore.exceptions.ResponseException(
            mock_response,
        )

        with patch.object(fetcher, "_get_reddit", return_value=mock_reddit):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "OAuth2" in result["error"]

    def test_connection_credentials_not_configured(self) -> None:
        config = _make_config(client_id="", client_secret="")
        fetcher = RedditFetcher(config=config)

        result = fetcher.test_connection()

        assert result["ok"] is False
        assert "凭证" in result["error"]

    def test_connection_generic_error(self, fetcher: RedditFetcher) -> None:
        mock_reddit = MagicMock()
        mock_reddit.user.me.side_effect = Exception("Unexpected failure")

        with patch.object(fetcher, "_get_reddit", return_value=mock_reddit):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "Unexpected failure" in result["error"]
