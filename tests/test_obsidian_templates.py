"""测试 Obsidian 模板渲染."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
import yaml

from ainews.publisher.obsidian_templates import (
    generate_slug,
    normalize_entity_name,
    render_article_body,
    render_article_frontmatter,
    render_daily_header,
    render_daily_section,
    render_dashboard_by_category,
    render_dashboard_daily_stats,
    render_dashboard_home,
    render_dashboard_knowledge_graph,
    render_dashboard_people_tracker,
    render_dashboard_reading_list,
    render_dashboard_trending,
    render_dashboard_weekly_stats,
    render_entity_page,
)


def _make_article(**overrides: object) -> SimpleNamespace:
    """创建测试用文章对象."""
    defaults = {
        "title": "GPT-6 Announced: Real-Time Reasoning Breakthrough",
        "url": "https://example.com/gpt6",
        "source": "hackernews",
        "source_name": "HackerNews",
        "author": "John Doe",
        "category": "industry",
        "summary_zh": "OpenAI 宣布了 GPT-6 模型",
        "relevance": 9.0,
        "tags": '["AI", "GPT", "LLM"]',
        "entities": '[{"name": "Sam Altman", "type": "person"}, {"name": "OpenAI", "type": "company"}, {"name": "GPT-6", "type": "project"}]',
        "trend_score": 8.5,
        "is_trending": True,
        "platforms": '["hackernews", "reddit"]',
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
    return SimpleNamespace(**defaults)


def _make_entity(**overrides: object) -> SimpleNamespace:
    """创建测试用实体对象."""
    defaults = {
        "id": 1,
        "name": "Sam Altman",
        "type": "person",
        "first_seen_at": datetime(2026, 4, 1),
        "mention_count": 28,
        "is_new": False,
        "meta_json": '{"company": "OpenAI"}',
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSlugGeneration:
    """slug 生成测试."""

    def test_standard_title(self) -> None:
        slug = generate_slug("GPT-6 Announced: Real-Time Reasoning Breakthrough")
        assert slug == "gpt-6-announced-real-time-reasoning-breakthrough"

    def test_title_with_special_chars(self) -> None:
        slug = generate_slug("AI's New $100B Market! (2026)")
        assert "$" not in slug
        assert "!" not in slug
        assert "(" not in slug

    def test_title_truncation(self) -> None:
        long_title = "A" * 100
        slug = generate_slug(long_title)
        assert len(slug) <= 60

    def test_chinese_title(self) -> None:
        slug = generate_slug("深度学习新架构：Transformer 的进化")
        # 中文字符被移除，结果可能为空
        assert isinstance(slug, str)

    def test_empty_title(self) -> None:
        slug = generate_slug("")
        assert slug == ""

    def test_title_with_spaces(self) -> None:
        slug = generate_slug("Hello World Test")
        assert slug == "hello-world-test"


class TestArticleFrontmatter:
    """文章 frontmatter 渲染测试."""

    def test_complete_frontmatter(self) -> None:
        article = _make_article()
        result = render_article_frontmatter(article)
        assert result.startswith("---\n")
        assert result.endswith("---")
        # 解析 YAML
        yaml_str = result[4:-4]  # 去掉 --- 包裹
        fm = yaml.safe_load(yaml_str)
        assert fm["title"] == article.title
        assert fm["category"] == "industry"
        assert fm["relevance"] == 9.0
        assert fm["is_trending"] is True
        assert "tags" in fm
        assert "entities" in fm

    def test_optional_fields_omitted(self) -> None:
        article = _make_article(author="")
        result = render_article_frontmatter(article)
        yaml_str = result[4:-4]
        fm = yaml.safe_load(yaml_str)
        assert "author" not in fm

    def test_entities_parsed(self) -> None:
        article = _make_article()
        result = render_article_frontmatter(article)
        yaml_str = result[4:-4]
        fm = yaml.safe_load(yaml_str)
        assert "person" in fm["entities"]
        assert "Sam Altman" in fm["entities"]["person"]


class TestArticleBody:
    """文章正文渲染测试."""

    def test_complete_body(self) -> None:
        article = _make_article()
        result = render_article_body(article)
        assert "## 中文摘要" in result
        assert "OpenAI 宣布了 GPT-6 模型" in result
        assert "## 原文链接" in result
        assert "## 关联" in result
        assert "[[Sam-Altman]]" in result
        assert "[[OpenAI]]" in result

    def test_no_entities(self) -> None:
        article = _make_article(entities="[]")
        result = render_article_body(article)
        assert "## 关联" not in result

    def test_no_summary(self) -> None:
        article = _make_article(summary_zh="")
        result = render_article_body(article)
        assert "## 中文摘要" not in result


class TestDailySection:
    """每日笔记段落渲染测试."""

    def test_daily_section(self) -> None:
        articles = [
            _make_article(
                title="Test Article",
                is_trending=True,
                relevance=9.0,
                category="industry",
            ),
        ]
        ts = datetime(2026, 4, 13, 8, 30)
        result = render_daily_section(articles, ts)
        assert "## 08:30 更新 (1篇)" in result
        assert "🔥" in result

    def test_daily_section_normal_article(self) -> None:
        articles = [
            _make_article(
                title="Normal Article",
                is_trending=False,
                relevance=7.0,
                category="research",
            ),
        ]
        ts = datetime(2026, 4, 13, 12, 0)
        result = render_daily_section(articles, ts)
        assert "## 12:00 更新 (1篇)" in result
        assert "🔥" not in result

    def test_daily_section_multiple(self) -> None:
        articles = [
            _make_article(title="A"),
            _make_article(title="B"),
        ]
        result = render_daily_section(articles, datetime(2026, 4, 13, 8, 0))
        assert "(2篇)" in result


class TestDailyHeader:
    """每日笔记头部渲染测试."""

    def test_daily_header_with_date(self) -> None:
        result = render_daily_header("2026-04-13")
        assert "# AI News - 2026-04-13" in result
        assert "dataview" in result

    def test_daily_header_default_date(self) -> None:
        result = render_daily_header()
        assert "# AI News -" in result
        assert "dataview" in result


class TestEntityPage:
    """实体页面渲染测试."""

    def test_person_entity(self) -> None:
        entity = _make_entity()
        result = render_entity_page(entity)
        assert "# Sam Altman" in result
        assert "type: person" in result
        assert "mention_count: 28" in result
        assert "dataview" in result
        assert "people" in result

    def test_company_entity(self) -> None:
        entity = _make_entity(
            name="OpenAI",
            type="company",
            meta_json="{}",
        )
        result = render_entity_page(entity)
        assert "# OpenAI" in result
        assert "type: company" in result
        assert "companies" in result

    def test_project_entity(self) -> None:
        entity = _make_entity(
            name="GPT-6",
            type="project",
            meta_json="{}",
        )
        result = render_entity_page(entity)
        assert "# GPT-6" in result
        assert "type: project" in result
        assert "projects" in result


class TestEntityNameNormalization:
    """实体名称规范化测试."""

    def test_space_to_hyphen(self) -> None:
        assert normalize_entity_name("Sam Altman") == "Sam-Altman"

    def test_special_chars_removed(self) -> None:
        assert normalize_entity_name("AlphaGo (DeepMind)") == "AlphaGo-DeepMind"

    def test_already_normalized(self) -> None:
        assert normalize_entity_name("GPT-6") == "GPT-6"

    def test_multiple_spaces(self) -> None:
        result = normalize_entity_name("John  Doe   Smith")
        assert " " not in result
        assert "--" not in result


class TestDashboardTemplates:
    """仪表盘模板测试."""

    def test_home_dashboard(self) -> None:
        result = render_dashboard_home()
        assert "Home" in result
        assert "dataview" in result

    def test_trending_dashboard(self) -> None:
        result = render_dashboard_trending()
        assert "Trending" in result
        assert "48" in result

    def test_daily_stats_dashboard(self) -> None:
        result = render_dashboard_daily_stats()
        assert "Daily Stats" in result

    def test_weekly_stats_dashboard(self) -> None:
        result = render_dashboard_weekly_stats()
        assert "Weekly Stats" in result

    def test_reading_list_dashboard(self) -> None:
        result = render_dashboard_reading_list()
        assert "Reading List" in result

    def test_people_tracker_dashboard(self) -> None:
        result = render_dashboard_people_tracker()
        assert "People Tracker" in result

    def test_knowledge_graph_dashboard(self) -> None:
        result = render_dashboard_knowledge_graph()
        assert "Knowledge Graph" in result

    def test_by_category_dashboard(self) -> None:
        result = render_dashboard_by_category()
        assert "By Category" in result
        assert "Industry" in result
        assert "Research" in result
        assert "Tools" in result

    def test_all_dashboards_non_empty(self) -> None:
        renderers = [
            render_dashboard_home,
            render_dashboard_trending,
            render_dashboard_daily_stats,
            render_dashboard_weekly_stats,
            render_dashboard_reading_list,
            render_dashboard_people_tracker,
            render_dashboard_knowledge_graph,
            render_dashboard_by_category,
        ]
        for renderer in renderers:
            content = renderer()
            assert len(content) > 100
            assert "```dataview" in content
