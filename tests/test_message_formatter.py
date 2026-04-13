"""测试消息格式构建器：feedCard / actionCard / markdown."""

from __future__ import annotations

from ainews.publisher.formatter import (
    build_actioncard,
    build_feedcard,
    build_markdown_noon,
    build_markdown_weekly,
    build_test_message,
)


class TestBuildFeedcard:
    """测试 feedCard 消息构建."""

    def test_basic_feedcard(self) -> None:
        """基本 feedCard 消息结构."""
        articles = [
            {"title": "Article 1", "url": "https://example.com/1"},
            {"title": "Article 2", "url": "https://example.com/2"},
        ]
        result = build_feedcard(articles, title="测试")

        assert result["msgtype"] == "feedCard"
        assert "feedCard" in result
        assert "links" in result["feedCard"]
        assert len(result["feedCard"]["links"]) == 2

    def test_feedcard_with_pic(self) -> None:
        """feedCard 包含图片 URL."""
        articles = [
            {
                "title": "Article 1",
                "url": "https://example.com/1",
                "pic_url": "https://example.com/img.png",
            },
        ]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert link["title"] == "Article 1"
        assert link["messageURL"] == "https://example.com/1"
        assert link["picURL"] == "https://example.com/img.png"

    def test_feedcard_without_pic(self) -> None:
        """feedCard 无图片 URL 时不包含 picURL 字段."""
        articles = [
            {"title": "Article 1", "url": "https://example.com/1"},
        ]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert "picURL" not in link

    def test_feedcard_empty_articles(self) -> None:
        """空文章列表."""
        result = build_feedcard([])
        assert result["msgtype"] == "feedCard"
        assert result["feedCard"]["links"] == []

    def test_feedcard_default_title(self) -> None:
        """默认标题."""
        result = build_feedcard([{"title": "A", "url": "http://x"}])
        assert result["msgtype"] == "feedCard"


class TestBuildActioncard:
    """测试 actionCard 消息构建."""

    def test_basic_actioncard(self) -> None:
        """基本 actionCard 结构."""
        article = {
            "title": "Test Article",
            "summary_zh": "这是一篇测试文章的摘要",
            "url": "https://example.com/1",
        }
        result = build_actioncard(article)

        assert result["msgtype"] == "actionCard"
        assert "actionCard" in result
        assert result["actionCard"]["title"] == "Test Article"
        assert "这是一篇测试文章的摘要" in result["actionCard"]["text"]
        assert len(result["actionCard"]["btns"]) == 1
        assert result["actionCard"]["btns"][0]["title"] == "阅读原文"

    def test_actioncard_with_obsidian(self) -> None:
        """actionCard 包含 Obsidian 按钮."""
        article = {
            "title": "Test",
            "summary_zh": "Summary",
            "url": "https://example.com/1",
            "obsidian_url": "obsidian://open?vault=test&file=article",
        }
        result = build_actioncard(article)
        assert len(result["actionCard"]["btns"]) == 2
        assert result["actionCard"]["btns"][1]["title"] == "查看 Obsidian"

    def test_actioncard_summary_truncation(self) -> None:
        """长摘要应被截断."""
        article = {
            "title": "Test",
            "summary_zh": "x" * 500,
            "url": "https://example.com/1",
        }
        result = build_actioncard(article)
        text = result["actionCard"]["text"]
        # 摘要部分应被截断（含 "### Test\n\n" 前缀 + 截断后摘要）
        assert len(result["actionCard"]["text"]) < 600

    def test_actioncard_contains_title_in_text(self) -> None:
        """markdown text 应包含标题."""
        article = {
            "title": "Breaking News",
            "summary_zh": "Summary here",
            "url": "https://example.com/1",
        }
        result = build_actioncard(article)
        assert "### Breaking News" in result["actionCard"]["text"]


class TestBuildMarkdownWeekly:
    """测试周报 markdown 消息构建."""

    def test_basic_weekly(self) -> None:
        """基本周报结构."""
        stats = {"total": 42, "categories": {"LLM": 20, "CV": 12, "NLP": 10}}
        top_articles = [
            {"title": "Hot Topic", "url": "https://example.com/1", "trend_score": 9.5},
        ]
        result = build_markdown_weekly(stats, top_articles)

        assert result["msgtype"] == "markdown"
        assert "markdown" in result
        assert result["markdown"]["title"] == "AI 周报"
        assert "42" in result["markdown"]["text"]
        assert "Hot Topic" in result["markdown"]["text"]

    def test_weekly_with_categories(self) -> None:
        """周报包含分类分布."""
        stats = {"total": 10, "categories": {"LLM": 7, "NLP": 3}}
        top_articles = []
        result = build_markdown_weekly(stats, top_articles)

        text = result["markdown"]["text"]
        assert "LLM" in text
        assert "NLP" in text
        assert "7 篇" in text

    def test_weekly_empty_stats(self) -> None:
        """空统计."""
        stats = {"total": 0, "categories": {}}
        result = build_markdown_weekly(stats, [])
        assert "0" in result["markdown"]["text"]

    def test_weekly_top5(self) -> None:
        """周报 Top 5 文章."""
        stats = {"total": 50, "categories": {}}
        articles = [
            {"title": f"Article {i}", "url": f"https://example.com/{i}", "trend_score": 10.0 - i}
            for i in range(5)
        ]
        result = build_markdown_weekly(stats, articles)
        text = result["markdown"]["text"]
        for i in range(5):
            assert f"Article {i}" in text


class TestBuildMarkdownNoon:
    """测试午间速报 markdown 消息构建."""

    def test_basic_noon(self) -> None:
        """基本午间速报结构."""
        articles = [
            {
                "title": "Hot AI",
                "url": "https://example.com/1",
                "trend_score": 9.0,
                "source_name": "HackerNews",
            },
        ]
        result = build_markdown_noon(articles)

        assert result["msgtype"] == "markdown"
        assert result["markdown"]["title"] == "午间速报 - AI 热点"
        assert "Hot AI" in result["markdown"]["text"]

    def test_noon_empty(self) -> None:
        """无热点文章."""
        result = build_markdown_noon([])
        assert "暂无新增热点" in result["markdown"]["text"]

    def test_noon_count(self) -> None:
        """午间速报包含条数统计."""
        articles = [
            {"title": f"Article {i}", "url": f"http://x/{i}", "trend_score": 8.5, "source_name": "S"}
            for i in range(3)
        ]
        result = build_markdown_noon(articles)
        assert "本次推送 3 条热点" in result["markdown"]["text"]


class TestBuildTestMessage:
    """测试测试消息构建."""

    def test_test_message(self) -> None:
        """测试消息结构."""
        result = build_test_message()
        assert result["msgtype"] == "markdown"
        assert "markdown" in result
        assert result["markdown"]["title"] == "AI News Tips 测试"
        assert "测试消息" in result["markdown"]["text"]
