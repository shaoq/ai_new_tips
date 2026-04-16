"""测试 more-sources 变更中的常量和配置扩展."""

from __future__ import annotations

from unittest.mock import MagicMock


# ------------------------------------------------------------------
# DEFAULT_RSS_FEEDS 扩展
# ------------------------------------------------------------------


class TestDefaultRSSFeeds:
    def test_feed_count(self) -> None:
        """DEFAULT_RSS_FEEDS 包含约 31 个条目."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        assert len(DEFAULT_RSS_FEEDS) >= 25

    def test_original_sources_present(self) -> None:
        """原始源仍然存在."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        expected_original = [
            "openai-blog",
            "deepmind",
            "huggingface",
            "marktechpost",
            "venturebeat-ai",
        ]
        for name in expected_original:
            assert name in DEFAULT_RSS_FEEDS, f"Missing original source: {name}"

    def test_reddit_rss_sources(self) -> None:
        """Reddit RSS 源."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        reddit_sources = [
            "reddit-machinelearning",
            "reddit-localllama",
            "reddit-chatgpt",
        ]
        for name in reddit_sources:
            assert name in DEFAULT_RSS_FEEDS, f"Missing Reddit RSS source: {name}"

    def test_anthropic_sources(self) -> None:
        """Anthropic 官方 RSS 源（via RSSHub）."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        assert "anthropic-news" in DEFAULT_RSS_FEEDS
        assert "anthropic-research" in DEFAULT_RSS_FEEDS

    def test_community_sources(self) -> None:
        """社区源."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        community_sources = [
            "reddit-claudeai",
            "reddit-anthropicai",
            "devto-claude",
        ]
        for name in community_sources:
            assert name in DEFAULT_RSS_FEEDS, f"Missing community source: {name}"

    def test_newsletter_blog_sources(self) -> None:
        """Newsletter / 博客源."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        blog_sources = [
            "developers-digest",
            "pragmatic-engineer",
            "ai-maker",
            "the-ai-corner",
            "alexop-dev",
            "codecentric",
            "changelog",
        ]
        for name in blog_sources:
            assert name in DEFAULT_RSS_FEEDS, f"Missing blog source: {name}"

    def test_chinese_sources(self) -> None:
        """中文源."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        assert "ccino-org" in DEFAULT_RSS_FEEDS
        assert "tony-bai" in DEFAULT_RSS_FEEDS
        assert "hellogithub" in DEFAULT_RSS_FEEDS

    def test_github_discovery_sources(self) -> None:
        """GitHub 仓库发现源."""
        from ainews.fetcher.rss import DEFAULT_RSS_FEEDS
        github_sources = [
            "github-trending-python-daily",
            "github-trending-all-weekly",
            "libhunt-python",
            "libhunt-selfhosted",
        ]
        for name in github_sources:
            assert name in DEFAULT_RSS_FEEDS, f"Missing GitHub discovery source: {name}"


# ------------------------------------------------------------------
# HackerNews AI_KEYWORDS 扩展
# ------------------------------------------------------------------


class TestHackerNewsKeywords:
    def test_new_agentic_keywords(self) -> None:
        """新增 Agentic coding 工具关键词."""
        from ainews.fetcher.hackernews import AI_KEYWORDS, _is_ai_related
        new_keywords = [
            "agentic", "cursor", "windsurf", "codex", "aider",
            "coding assistant", "computer use",
        ]
        for kw in new_keywords:
            assert kw in AI_KEYWORDS, f"Missing keyword: {kw}"

    def test_new_keywords_detect_ai_titles(self) -> None:
        """新关键词正确检测 AI 相关标题."""
        from ainews.fetcher.hackernews import _is_ai_related
        assert _is_ai_related("Cursor AI editor review") is True
        assert _is_ai_related("Windsurf vs Cursor comparison") is True
        assert _is_ai_related("Codex CLI coding assistant") is True
        assert _is_ai_related("Aider AI pair programming") is True
        assert _is_ai_related("Computer use with Claude") is True
        assert _is_ai_related("Agentic workflows in production") is True

    def test_original_keywords_still_present(self) -> None:
        """原始关键词仍然存在."""
        from ainews.fetcher.hackernews import AI_KEYWORDS
        original = [
            "ai", "llm", "gpt", "claude", "gemini", "machine learning",
            "openai", "anthropic", "deepmind", "transformer", "rag",
        ]
        for kw in original:
            assert kw in AI_KEYWORDS, f"Missing original keyword: {kw}"


# ------------------------------------------------------------------
# ArXiv DEFAULT_CATEGORIES 扩展
# ------------------------------------------------------------------


class TestArXivCategories:
    def test_default_categories_includes_new(self) -> None:
        """DEFAULT_CATEGORIES 包含 cs.CV 和 stat.ML."""
        from ainews.fetcher.arxiv import DEFAULT_CATEGORIES
        assert "cs.CV" in DEFAULT_CATEGORIES
        assert "stat.ML" in DEFAULT_CATEGORIES

    def test_default_categories_includes_original(self) -> None:
        """DEFAULT_CATEGORIES 包含原始分类."""
        from ainews.fetcher.arxiv import DEFAULT_CATEGORIES
        assert "cs.AI" in DEFAULT_CATEGORIES
        assert "cs.LG" in DEFAULT_CATEGORIES
        assert "cs.CL" in DEFAULT_CATEGORIES

    def test_total_category_count(self) -> None:
        """总计 5 个分类."""
        from ainews.fetcher.arxiv import DEFAULT_CATEGORIES
        assert len(DEFAULT_CATEGORIES) == 5


# ------------------------------------------------------------------
# RedditConfig 默认 subreddits
# ------------------------------------------------------------------


class TestRedditDefaults:
    def test_default_subreddits_includes_new(self) -> None:
        """RedditConfig 默认 subreddits 包含新增的."""
        from ainews.config.settings import RedditConfig
        cfg = RedditConfig()
        assert "artificial" in cfg.subreddits
        assert "deeplearning" in cfg.subreddits
        assert "ClaudeAI" in cfg.subreddits

    def test_default_subreddits_includes_original(self) -> None:
        """RedditConfig 默认 subreddits 包含原始的."""
        from ainews.config.settings import RedditConfig
        cfg = RedditConfig()
        assert "MachineLearning" in cfg.subreddits
        assert "LocalLLaMA" in cfg.subreddits
        assert "ChatGPT" in cfg.subreddits

    def test_default_subreddit_count(self) -> None:
        """默认 6 个 subreddits."""
        from ainews.config.settings import RedditConfig
        cfg = RedditConfig()
        assert len(cfg.subreddits) == 6


# ------------------------------------------------------------------
# Chinese DEFAULT_CHINESE_SOURCES
# ------------------------------------------------------------------


class TestChineseDefaults:
    def test_default_chinese_sources(self) -> None:
        """DEFAULT_CHINESE_SOURCES 包含三个默认源."""
        from ainews.fetcher.chinese import DEFAULT_CHINESE_SOURCES
        names = {s["name"] for s in DEFAULT_CHINESE_SOURCES}
        assert "qbitai" in names
        assert "jiqizhixin" in names
        assert "aibase" in names

    def test_default_chinese_sources_count(self) -> None:
        """默认 3 个中文源."""
        from ainews.fetcher.chinese import DEFAULT_CHINESE_SOURCES
        assert len(DEFAULT_CHINESE_SOURCES) == 3

    def test_default_chinese_sources_all_rss(self) -> None:
        """默认中文源都是 RSS 方式."""
        from ainews.fetcher.chinese import DEFAULT_CHINESE_SOURCES
        for source in DEFAULT_CHINESE_SOURCES:
            assert source["method"] == "rss"
            assert source["url"] != ""


# ------------------------------------------------------------------
# Twitter DEFAULT_SEARCH_QUERY
# ------------------------------------------------------------------


class TestTwitterDefaults:
    def test_default_search_query_includes_claude_code(self) -> None:
        """DEFAULT_SEARCH_QUERY 包含 'claude code'."""
        from ainews.fetcher.twitter import DEFAULT_SEARCH_QUERY
        assert "claude code" in DEFAULT_SEARCH_QUERY

    def test_default_search_query_includes_cursor_ai(self) -> None:
        """DEFAULT_SEARCH_QUERY 包含 'cursor ai'."""
        from ainews.fetcher.twitter import DEFAULT_SEARCH_QUERY
        assert "cursor ai" in DEFAULT_SEARCH_QUERY

    def test_default_search_query_min_faves(self) -> None:
        """DEFAULT_SEARCH_QUERY 包含最低点赞数过滤."""
        from ainews.fetcher.twitter import DEFAULT_SEARCH_QUERY
        assert "min_faves" in DEFAULT_SEARCH_QUERY


# ------------------------------------------------------------------
# GitHub Releases DEFAULT_REPOS
# ------------------------------------------------------------------


class TestGitHubReleasesDefaults:
    def test_default_repos_count(self) -> None:
        """DEFAULT_REPOS 包含 12 个仓库."""
        from ainews.fetcher.github_releases import DEFAULT_REPOS
        assert len(DEFAULT_REPOS) == 12

    def test_default_repos_anthropic(self) -> None:
        """DEFAULT_REPOS 包含 Anthropic 官方仓库."""
        from ainews.fetcher.github_releases import DEFAULT_REPOS
        assert "anthropics/claude-code" in DEFAULT_REPOS
        assert "anthropics/anthropic-sdk-python" in DEFAULT_REPOS
        assert "anthropics/courses" in DEFAULT_REPOS

    def test_default_repos_resources(self) -> None:
        """DEFAULT_REPOS 包含资源/指南类仓库."""
        from ainews.fetcher.github_releases import DEFAULT_REPOS
        resource_repos = [
            "e2b-dev/awesome-ai-agents",
            "taishi-i/awesome-ChatGPT-repositories",
            "lukasmasuch/best-of-ml-python",
            "FlorianBruniaux/claude-code-ultimate-guide",
        ]
        for repo in resource_repos:
            assert repo in DEFAULT_REPOS, f"Missing resource repo: {repo}"

    def test_default_repos_discovery(self) -> None:
        """DEFAULT_REPOS 包含 GitHub 仓库推荐类."""
        from ainews.fetcher.github_releases import DEFAULT_REPOS
        discovery_repos = [
            "GitHubDaily/GitHubDaily",
            "OpenGithubs/weekly",
            "OpenGithubs/github-weekly-rank",
            "GrowingGit/GitHub-Chinese-Top-Charts",
            "EvanLi/Github-Ranking",
        ]
        for repo in discovery_repos:
            assert repo in DEFAULT_REPOS, f"Missing discovery repo: {repo}"


# ------------------------------------------------------------------
# GitHubReleasesConfig in settings.py
# ------------------------------------------------------------------


class TestGitHubReleasesConfig:
    def test_config_exists(self) -> None:
        """GitHubReleasesConfig 类存在."""
        from ainews.config.settings import GitHubReleasesConfig
        cfg = GitHubReleasesConfig()
        assert cfg.enabled is True
        assert cfg.token == ""
        assert cfg.repos == []
        assert cfg.fetch_interval_minutes == 360

    def test_config_custom_values(self) -> None:
        """GitHubReleasesConfig 接受自定义值."""
        from ainews.config.settings import GitHubReleasesConfig
        cfg = GitHubReleasesConfig(
            enabled=False,
            token="ghp_test123",
            repos=["org/repo"],
            fetch_interval_minutes=60,
        )
        assert cfg.enabled is False
        assert cfg.token == "ghp_test123"
        assert cfg.repos == ["org/repo"]
        assert cfg.fetch_interval_minutes == 60


# ------------------------------------------------------------------
# SourcesConfig has github_releases field
# ------------------------------------------------------------------


class TestSourcesConfig:
    def test_sources_has_github_releases(self) -> None:
        """SourcesConfig 包含 github_releases 字段."""
        from ainews.config.settings import SourcesConfig
        cfg = SourcesConfig()
        assert hasattr(cfg, "github_releases")
        assert isinstance(cfg.github_releases, type(cfg.github_releases))

    def test_sources_github_releases_default_enabled(self) -> None:
        """SourcesConfig.github_releases 默认启用."""
        from ainews.config.settings import SourcesConfig
        cfg = SourcesConfig()
        assert cfg.github_releases.enabled is True

    def test_sources_all_fetcher_fields(self) -> None:
        """SourcesConfig 包含所有 fetcher 配置字段."""
        from ainews.config.settings import SourcesConfig
        cfg = SourcesConfig()
        expected_fields = [
            "hackernews", "arxiv", "reddit", "hf_papers",
            "github", "github_releases", "chinese", "rss", "twitter",
        ]
        for field in expected_fields:
            assert hasattr(cfg, field), f"SourcesConfig missing field: {field}"


# ------------------------------------------------------------------
# Registry has github-releases
# ------------------------------------------------------------------


class TestRegistry:
    def test_github_releases_registered(self) -> None:
        """Registry 注册了 github-releases."""
        from ainews.fetcher.registry import is_registered
        assert is_registered("github-releases") is True

    def test_all_sources_registered(self) -> None:
        """所有内置数据源都已注册."""
        from ainews.fetcher.registry import is_registered
        expected = [
            "hackernews", "arxiv", "rss", "reddit",
            "hf_papers", "github", "chinese", "twitter",
            "github-releases",
        ]
        for name in expected:
            assert is_registered(name) is True, f"Source not registered: {name}"

    def test_get_fetcher_github_releases(self) -> None:
        """get_fetcher 能返回 GitHubReleasesFetcher 实例."""
        from ainews.fetcher.registry import get_fetcher
        from ainews.fetcher.github_releases import GitHubReleasesFetcher

        cfg = MagicMock()
        cfg.repos = []
        fetcher = get_fetcher("github-releases", config=cfg)
        assert isinstance(fetcher, GitHubReleasesFetcher)
