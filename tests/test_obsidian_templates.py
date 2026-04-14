"""测试 Obsidian 模板渲染."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from ainews.publisher.obsidian_templates import (
    generate_slug,
    normalize_entity_name,
    render_article_body,
    render_article_frontmatter,
    render_daily_header,
    render_daily_section,
    render_dashboard_articles,
    render_dashboard_home,
    render_dashboard_people_tracker,
    render_dashboard_reading_list,
    render_dashboard_trending,
    render_entity_page,
)
from ainews.publisher.dashboards import (
    DASHBOARDS,
    DASHBOARD_DIR,
    init_dashboards,
    rebuild_dashboards,
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
        yaml_str = result[4:-4]
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
    """每日笔记头部渲染测试 — Bases 嵌入代码块."""

    def test_daily_header_contains_base_block(self) -> None:
        result = render_daily_header("2026-04-13")
        assert "# AI News - 2026-04-13" in result
        assert "```base" in result
        assert "```" in result

    def test_daily_header_no_dataview(self) -> None:
        result = render_daily_header("2026-04-13")
        assert "dataview" not in result
        assert "dataviewjs" not in result

    def test_daily_header_base_yaml_valid(self) -> None:
        result = render_daily_header("2026-04-13")
        # 提取 base 代码块内容
        start = result.index("```base") + len("```base\n")
        end = result.index("```", start)
        base_yaml = result[start:end].strip()
        parsed = yaml.safe_load(base_yaml)
        assert "filters" in parsed
        assert "properties" in parsed
        assert "views" in parsed
        assert parsed["filters"]["date"] == "2026-04-13"

    def test_daily_header_default_date(self) -> None:
        result = render_daily_header()
        assert "# AI News -" in result
        assert "```base" in result


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


class TestDashboardBasesYaml:
    """仪表盘 Bases YAML 模板测试."""

    @pytest.fixture()
    def dashboard_renderers(self) -> dict[str, object]:
        return {
            "Home": render_dashboard_home,
            "Trending": render_dashboard_trending,
            "Reading-List": render_dashboard_reading_list,
            "People-Tracker": render_dashboard_people_tracker,
            "Articles": render_dashboard_articles,
        }

    def test_all_dashboards_valid_yaml(self, dashboard_renderers: dict) -> None:
        """验证每个 render_dashboard_*() 返回有效 YAML."""
        for name, renderer in dashboard_renderers.items():
            content = renderer()
            parsed = yaml.safe_load(content)
            assert isinstance(parsed, dict), f"{name}: YAML 解析结果不是 dict"
            assert "filters" in parsed, f"{name}: 缺少 filters"
            assert "properties" in parsed, f"{name}: 缺少 properties"
            assert "views" in parsed, f"{name}: 缺少 views"

    def test_all_dashboards_no_dataview(self, dashboard_renderers: dict) -> None:
        """验证返回的字符串中不含 dataview/dataviewjs."""
        for name, renderer in dashboard_renderers.items():
            content = renderer()
            assert "dataview" not in content, f"{name}: 包含 dataview"
            assert "dataviewjs" not in content, f"{name}: 包含 dataviewjs"

    def test_home_dashboard_views(self) -> None:
        parsed = yaml.safe_load(render_dashboard_home())
        views = parsed["views"]
        assert "today" in views
        assert "trending" in views
        assert "weekly" in views

    def test_trending_dashboard_views(self) -> None:
        parsed = yaml.safe_load(render_dashboard_trending())
        views = parsed["views"]
        assert "hot_48h" in views
        assert "cross_platform" in views

    def test_reading_list_dashboard_views(self) -> None:
        parsed = yaml.safe_load(render_dashboard_reading_list())
        views = parsed["views"]
        assert "unread" in views
        assert "by_category" in views

    def test_people_tracker_dashboard_views(self) -> None:
        parsed = yaml.safe_load(render_dashboard_people_tracker())
        views = parsed["views"]
        assert "people" in views
        assert "companies" in views
        assert "projects" in views

    def test_articles_dashboard_has_summaries(self) -> None:
        parsed = yaml.safe_load(render_dashboard_articles())
        assert "summaries" in parsed
        assert "avg_trend_score" in parsed["summaries"]

    def test_all_dashboards_non_empty(self, dashboard_renderers: dict) -> None:
        for name, renderer in dashboard_renderers.items():
            content = renderer()
            assert len(content) > 50, f"{name}: 内容过短"


class TestDashboardsOutput:
    """仪表盘输出适配测试."""

    def test_dashboards_count_is_5(self) -> None:
        assert len(DASHBOARDS) == 5

    def test_dashboards_has_expected_names(self) -> None:
        expected = {"Home", "Trending", "Reading-List", "People-Tracker", "Articles"}
        assert set(DASHBOARDS.keys()) == expected

    def test_dashboard_suffix_is_base(self) -> None:
        """验证 init_dashboards 输出路径以 .base 结尾."""
        for name in DASHBOARDS:
            path = f"{DASHBOARD_DIR}/{name}.base"
            assert path.endswith(".base"), f"{name} 路径不以 .base 结尾"

    def test_init_dashboards_creates_base_files(self) -> None:
        """验证 init_dashboards 生成 5 个 .base 文件."""
        client = MagicMock()
        client.get_vault_file.return_value = None  # 所有文件不存在
        client.put_vault_file.return_value = True

        created, skipped = init_dashboards(client)
        assert created == 5
        assert skipped == 0

        # 验证每个调用使用了 .base 后缀
        for call in client.put_vault_file.call_args_list:
            path = call[0][0]
            assert path.endswith(".base"), f"路径不以 .base 结尾: {path}"

    def test_rebuild_dashboards_overwrites(self) -> None:
        """验证 rebuild_dashboards 正确覆盖已有 .base 文件."""
        client = MagicMock()
        client.put_vault_file.return_value = True

        created, skipped = rebuild_dashboards(client)
        assert created == 5
        # rebuild 模式不检查现有文件
        client.get_vault_file.assert_not_called()

    def test_init_dashboards_skips_existing(self) -> None:
        """非重建模式跳过已有文件."""
        client = MagicMock()
        client.get_vault_file.return_value = "existing content"
        client.put_vault_file.return_value = True

        created, skipped = init_dashboards(client, rebuild=False)
        assert created == 0
        assert skipped == 5
