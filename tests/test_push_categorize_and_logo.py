"""Tests for source_type mapping and push formatting."""

from __future__ import annotations

import pytest

from ainews.publisher.source_map import (
    get_favicon_url,
    get_source_type,
    get_source_type_label,
)
from ainews.publisher.formatter import (
    build_feedcard,
    build_markdown_noon,
    build_markdown_weekly,
)


# ---------------------------------------------------------------------------
# source_map tests
# ---------------------------------------------------------------------------


class TestGetSourceType:
    """Task 4.1: source_type 映射正确性."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("hackernews", "article"),
            ("reddit", "article"),
            ("rss", "article"),
            ("chinese", "article"),
            ("twitter", "article"),
            ("arxiv", "paper"),
            ("hf_papers", "paper"),
            ("github", "repo"),
            ("github-releases", "repo"),
        ],
    )
    def test_known_source(self, source: str, expected: str) -> None:
        assert get_source_type(source) == expected

    def test_unknown_source_defaults_to_article(self) -> None:
        assert get_source_type("unknown_source") == "article"

    def test_empty_source_defaults_to_article(self) -> None:
        assert get_source_type("") == "article"


class TestGetSourceTypeLabel:
    def test_article_label(self) -> None:
        assert get_source_type_label("article") == "文章"

    def test_paper_label(self) -> None:
        assert get_source_type_label("paper") == "论文"

    def test_repo_label(self) -> None:
        assert get_source_type_label("repo") == "仓库"

    def test_unknown_defaults_to_article_label(self) -> None:
        assert get_source_type_label("unknown") == "文章"


class TestGetFaviconUrl:
    def test_known_source_returns_url(self) -> None:
        url = get_favicon_url("arxiv")
        assert "arxiv.org" in url

    def test_github_returns_github_domain(self) -> None:
        url = get_favicon_url("github")
        assert "github.com" in url

    def test_unknown_source_returns_fallback(self) -> None:
        url = get_favicon_url("nonexistent")
        assert "venturebeat.com" in url

    def test_blocked_source_returns_accessible_icon(self) -> None:
        url = get_favicon_url("reddit")
        assert "flaticon.com" in url
        url2 = get_favicon_url("twitter")
        assert "flaticon.com" in url2


# ---------------------------------------------------------------------------
# build_feedcard tests (Task 4.2)
# ---------------------------------------------------------------------------


class TestBuildFeedcard:
    def _make_article(
        self,
        title: str = "Test",
        url: str = "https://example.com",
        source_type: str = "article",
        pic_url: str = "https://img.example.com/favicon.ico",
        trend_score: float = 5.0,
    ) -> dict:
        return {
            "title": title,
            "title_zh": title,
            "url": url,
            "source_type": source_type,
            "pic_url": pic_url,
            "trend_score": trend_score,
        }

    def test_title_prefix_article(self) -> None:
        articles = [self._make_article(title="OpenAI 发布 GPT-5", source_type="article")]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert link["title"] == "[文章] OpenAI 发布 GPT-5"

    def test_title_prefix_paper(self) -> None:
        articles = [self._make_article(title="Transformer 新架构", source_type="paper")]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert link["title"] == "[论文] Transformer 新架构"

    def test_title_prefix_repo(self) -> None:
        articles = [self._make_article(title="anthropics/claude-code", source_type="repo")]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert link["title"] == "[仓库] anthropics/claude-code"

    def test_picurl_populated(self) -> None:
        articles = [self._make_article(pic_url="https://github.com/favicon.ico")]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert link["picURL"] == "https://github.com/favicon.ico"

    def test_picurl_omitted_when_empty(self) -> None:
        articles = [self._make_article(pic_url="")]
        result = build_feedcard(articles)
        link = result["feedCard"]["links"][0]
        assert "picURL" not in link

    def test_sort_by_source_type_then_trend_score(self) -> None:
        articles = [
            self._make_article(title="Repo A", source_type="repo", trend_score=9.0),
            self._make_article(title="Article B", source_type="article", trend_score=5.0),
            self._make_article(title="Paper C", source_type="paper", trend_score=8.0),
            self._make_article(title="Article D", source_type="article", trend_score=7.0),
        ]
        result = build_feedcard(articles)
        titles = [link["title"] for link in result["feedCard"]["links"]]
        assert titles[0] == "[文章] Article D"  # article, score 7.0
        assert titles[1] == "[文章] Article B"  # article, score 5.0
        assert titles[2] == "[论文] Paper C"    # paper, score 8.0
        assert titles[3] == "[仓库] Repo A"     # repo, score 9.0


# ---------------------------------------------------------------------------
# build_markdown tests (Task 4.3)
# ---------------------------------------------------------------------------


class TestBuildMarkdownNoon:
    def test_source_type_label_in_output(self) -> None:
        articles = [
            {
                "title": "GPT-5 Paper",
                "title_zh": "GPT-5 论文",
                "url": "https://arxiv.org/abs/2401.0001",
                "trend_score": 8.5,
                "source_name": "ArXiv",
                "source_type": "paper",
            },
        ]
        result = build_markdown_noon(articles)
        text = result["markdown"]["text"]
        assert "[论文]" in text

    def test_article_type_label(self) -> None:
        articles = [
            {
                "title": "OpenAI Blog",
                "title_zh": "OpenAI 博客",
                "url": "https://openai.com/blog",
                "trend_score": 9.0,
                "source_name": "OpenAI Blog",
                "source_type": "article",
            },
        ]
        result = build_markdown_noon(articles)
        text = result["markdown"]["text"]
        assert "[文章]" in text


class TestBuildMarkdownWeekly:
    def test_source_type_label_in_weekly(self) -> None:
        top_articles = [
            {
                "title": "Claude Code v2",
                "title_zh": "Claude Code v2",
                "url": "https://github.com/anthropics/claude-code",
                "trend_score": 9.5,
                "source_type": "repo",
            },
        ]
        stats = {"total": 42, "categories": {"tools": 20, "research": 22}}
        result = build_markdown_weekly(stats, top_articles)
        text = result["markdown"]["text"]
        assert "[仓库]" in text
