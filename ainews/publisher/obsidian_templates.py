"""Obsidian Markdown 模板渲染."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import yaml


def render_article_frontmatter(article: Any) -> str:
    """生成文章 YAML frontmatter.

    Args:
        article: Article 模型实例，包含所有文章字段
    """
    tags: list[str] = _parse_json_field(article.tags, [])
    platforms: list[str] = _parse_json_field(article.platforms, [])
    entities_raw: Any = _parse_json_field(article.entities, {})

    # 将 entities 按类型分组
    entities: dict[str, list[str]] = {}
    if isinstance(entities_raw, list):
        for ent in entities_raw:
            if isinstance(ent, dict):
                ent_type = ent.get("type", "unknown")
                ent_name = ent.get("name", "")
                if ent_name:
                    entities.setdefault(ent_type, []).append(ent_name)
    elif isinstance(entities_raw, dict):
        entities = entities_raw

    fm: dict[str, Any] = {
        "title": article.title,
        "date": _fmt_date(article.published_at),
        "source": article.source,
        "source_name": article.source_name,
        "tags": tags,
        "category": article.category,
        "status": article.status,
        "relevance": article.relevance,
        "trend_score": article.trend_score,
        "is_trending": article.is_trending,
        "summary": article.summary_zh,
        "platforms": platforms,
        "entities": entities,
        "imported_at": _fmt_date(article.imported_at),
        "dingtalk_sent": article.dingtalk_sent,
    }

    if article.author:
        fm["author"] = article.author

    # 移除空值
    fm = {k: v for k, v in fm.items() if v not in (None, "", [], {})}

    frontmatter_str = yaml.dump(
        fm, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    return f"---\n{frontmatter_str}---"


def render_article_body(article: Any) -> str:
    """生成文章 Markdown 正文.

    包含: 中文摘要、原文链接、关联实体(双链)
    """
    parts: list[str] = []

    # 中文摘要
    if article.summary_zh:
        parts.append("## 中文摘要\n")
        parts.append(article.summary_zh)
        parts.append("")

    # 原文链接
    parts.append("## 原文链接\n")
    parts.append(f"[{article.title}]({article.url})")
    parts.append("")

    # 关联实体（双链）
    entities_raw = _parse_json_field(article.entities, [])
    entity_links: list[str] = []
    if isinstance(entities_raw, list):
        for ent in entities_raw:
            if isinstance(ent, dict):
                name = ent.get("name", "")
                if name:
                    link_name = normalize_entity_name(name)
                    entity_links.append(f"- [[{link_name}]]")
            elif isinstance(ent, str) and ent:
                link_name = normalize_entity_name(ent)
                entity_links.append(f"- [[{link_name}]]")

    if entity_links:
        parts.append("## 关联\n")
        parts.extend(entity_links)
        parts.append("")

    return "\n".join(parts)


def render_daily_section(
    articles: list[Any], timestamp: datetime | None = None
) -> str:
    """生成每日笔记更新段落.

    Args:
        articles: 本次同步的文章列表
        timestamp: 当前时间戳（用于生成 heading）
    """
    if timestamp is None:
        timestamp = datetime.now()

    time_str = timestamp.strftime("%H:%M")
    count = len(articles)
    lines: list[str] = [f"## {time_str} 更新 ({count}篇)\n"]

    for article in articles:
        slug = generate_slug(article.title)
        date_prefix = _fmt_date_prefix(article.published_at)
        link_target = f"{date_prefix}{slug}"

        # 截断标题作为显示文本
        short_title = article.title[:40] + ("..." if len(article.title) > 40 else "")

        # 热点标记
        trending = " 🔥" if article.is_trending else ""

        line = (
            f"- [[{link_target}|{short_title}]]"
            f"{trending} {article.relevance} {article.category}"
        )
        lines.append(line)

    lines.append("")
    return "\n".join(lines)


def render_daily_header(date: str | None = None) -> str:
    """生成每日笔记头部.

    Args:
        date: 日期字符串 YYYY-MM-DD，默认当天
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    base_yaml = (
        "filters:\n"
        "  and:\n"
        "    - file.inFolder(\"AI-News\")\n"
        f"    - 'date == date(\"{date}\")'\n"
        "formulas:\n"
        "  is_read: 'status == \"read\"'\n"
        "properties:\n"
        "  formula.is_read:\n"
        "    displayName: Read\n"
        "  source_name:\n"
        "    displayName: Source\n"
        "  category:\n"
        "    displayName: Category\n"
        "views:\n"
        "  - type: table\n"
        "    name: Overview\n"
        "    order:\n"
        "      - file.name\n"
        "      - relevance\n"
        "      - source_name\n"
        "      - category\n"
        "      - formula.is_read\n"
    )

    parts: list[str] = [
        f"# AI News - {date}\n",
        "## 概览\n",
        "```base",
        base_yaml,
        "```\n",
    ]
    return "\n".join(parts)


def render_entity_page(
    entity: Any,
    articles: list[Any] | None = None,
) -> str:
    """生成实体页面.

    Args:
        entity: Entity 模型实例
        articles: 关联文章列表（用于统计）
    """
    entity_name = entity.name
    file_name = normalize_entity_name(entity_name)
    entity_type = entity.type  # person/company/project/technology

    type_map: dict[str, str] = {
        "person": "person",
        "company": "company",
        "project": "project",
        "technology": "technology",
    }
    type_label = type_map.get(entity_type, entity_type)

    frontmatter: dict[str, Any] = {
        "type": type_label,
        "first_seen": _fmt_date(entity.first_seen_at),
        "mention_count": entity.mention_count,
        "last_seen": _fmt_date(
            articles[0].published_at if articles and articles[0].published_at
            else entity.first_seen_at
        ),
    }

    # 人物实体添加 company 字段
    if entity_type == "person":
        company = _extract_company_from_meta(entity.meta_json)
        if company:
            frontmatter["company"] = f"[[{normalize_entity_name(company)}]]"

    fm_str = yaml.dump(
        frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False
    )

    # Dataview 查询按实体类型
    entity_field_map: dict[str, str] = {
        "person": "people",
        "company": "companies",
        "project": "projects",
    }
    entity_field = entity_field_map.get(entity_type, entity_type)

    parts: list[str] = [
        f"---\n{fm_str}---\n",
        f"# {entity_name}\n",
        f"- **类型**: {type_label}",
        f"- **首次出现**: {frontmatter['first_seen']}",
        f"- **提及次数**: {entity.mention_count}\n",
        "## 相关文章\n",
        "```dataview",
        f"LIST FROM \"AI-News\"",
        f'WHERE contains(entities.{entity_field}, "{file_name}")',
        "SORT date DESC",
        "LIMIT 10",
        "```\n",
    ]
    return "\n".join(parts)


# ---- 仪表盘模板 (Obsidian Bases YAML) ----


def render_dashboard_home() -> str:
    """Home 仪表盘: 今日概览 / 今日热点 / 最近 7 天趋势."""
    return """\
filters:
  and:
    - file.inFolder("AI-News")
formulas:
  is_read: 'status == "read"'
properties:
  formula.is_read:
    displayName: Read
  source_name:
    displayName: Source
  category:
    displayName: Category
views:
  - type: table
    name: Today
    filters:
      and:
        - 'date == today()'
    order:
      - file.name
      - relevance
      - source_name
      - category
      - formula.is_read
  - type: table
    name: Trending
    filters:
      and:
        - is_trending
        - 'date >= today() - "1 day"'
    order:
      - file.name
      - relevance
      - source_name
      - category
  - type: table
    name: 7-Day Trend
    filters:
      and:
        - 'date >= today() - "7 days"'
    order:
      - file.name
      - date
      - relevance
      - source_name
      - category
      - is_trending
"""


def render_dashboard_trending() -> str:
    """Trending 仪表盘: 48h 热点 + 跨平台热点."""
    return """\
filters:
  and:
    - file.inFolder("AI-News")
properties:
  category:
    displayName: Category
views:
  - type: table
    name: 48h Hot
    filters:
      and:
        - is_trending
        - 'date >= today() - "2 days"'
    order:
      - file.name
      - relevance
      - category
      - date
  - type: table
    name: Cross-Platform
    filters:
      and:
        - 'length(platforms) >= 3'
        - 'date >= today() - "7 days"'
    order:
      - file.name
      - platforms
      - trend_score
      - category
      - date
"""


def render_dashboard_reading_list() -> str:
    """Reading-List 仪表盘: 未读列表 + 按分类浏览."""
    return """\
filters:
  and:
    - file.inFolder("AI-News")
formulas:
  is_read: 'status == "read"'
properties:
  formula.is_read:
    displayName: Read
  category:
    displayName: Category
views:
  - type: table
    name: Unread
    filters:
      and:
        - 'status != "read"'
    order:
      - file.name
      - relevance
      - category
      - date
      - formula.is_read
  - type: table
    name: By Category
    groupBy:
      property: category
      direction: ASC
    order:
      - file.name
      - category
      - relevance
      - date
      - formula.is_read
"""


def render_dashboard_people_tracker() -> str:
    """People-Tracker 仪表盘: People / Companies / Projects."""
    return """\
filters:
  and:
    - file.inFolder("AI-News/Entities")
properties:
  type:
    displayName: Type
  mention_count:
    displayName: Mentions
  last_seen:
    displayName: Last Seen
views:
  - type: table
    name: People
    filters:
      and:
        - 'type == "person"'
    order:
      - file.name
      - mention_count
      - last_seen
  - type: table
    name: Companies
    filters:
      and:
        - 'type == "company"'
    order:
      - file.name
      - mention_count
      - last_seen
  - type: table
    name: Projects
    filters:
      and:
        - 'type == "project"'
    order:
      - file.name
      - mention_count
      - last_seen
"""


def render_dashboard_articles() -> str:
    """Articles 仪表盘: 全量文章数据库视图，含 trend_score Average 汇总."""
    return """\
filters:
  and:
    - file.inFolder("AI-News")
formulas:
  is_read: 'status == "read"'
properties:
  formula.is_read:
    displayName: Read
  source_name:
    displayName: Source
  category:
    displayName: Category
views:
  - type: table
    name: All Articles
    order:
      - file.name
      - date
      - relevance
      - trend_score
      - category
      - source_name
      - formula.is_read
      - is_trending
    summaries:
      trend_score: Average
      relevance: Average
  - type: table
    name: By Source
    groupBy:
      property: source_name
      direction: ASC
    order:
      - source_name
      - file.name
      - date
      - relevance
      - category
      - formula.is_read
"""


def normalize_entity_name(name: str) -> str:
    """规范化实体名称为有效文件名/链接名.

    空格转连字符，移除特殊字符（保留字母、数字、连字符）.
    """
    # 移除括号但保留内容
    result = re.sub(r"[()]", "", name)
    # 空格转连字符
    result = result.replace(" ", "-")
    # 仅保留字母、数字、连字符
    result = re.sub(r"[^a-zA-Z0-9\-]", "", result)
    # 合并连续连字符
    result = re.sub(r"-+", "-", result)
    # 移除首尾连字符
    result = result.strip("-")
    return result


# ---- 辅助函数 ----

def generate_slug(title: str) -> str:
    """从标题生成 slug.

    小写化、移除非字母数字字符、空格转连字符、截断 60 字符.
    """
    slug = title.lower()
    # 移除非字母数字字符（保留空格和连字符）
    slug = re.sub(r"[^a-z0-9\s\-]", "", slug)
    # 空格转连字符
    slug = re.sub(r"\s+", "-", slug)
    # 合并连续连字符
    slug = re.sub(r"-+", "-", slug)
    # 移除首尾连字符
    slug = slug.strip("-")
    # 截断 60 字符
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")
    return slug


def _parse_json_field(value: str, default: Any) -> Any:
    """安全解析 JSON 字段."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _fmt_date(dt: datetime | None) -> str:
    """格式化日期为 YYYY-MM-DD."""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")


def _fmt_date_prefix(dt: datetime | None) -> str:
    """生成日期前缀 slug 部分 (YYYY-MM-DD-)."""
    if dt is None:
        now = datetime.now()
        return now.strftime("%Y-%m-%d-")
    return dt.strftime("%Y-%m-%d-")


def _extract_company_from_meta(meta_json: str) -> str:
    """从 meta_json 中提取公司名."""
    if not meta_json:
        return ""
    try:
        meta = json.loads(meta_json)
        return meta.get("company", "")
    except (json.JSONDecodeError, TypeError):
        return ""
