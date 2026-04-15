"""消息格式构建器：feedCard / actionCard / markdown."""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# 2.1 feedCard 消息（晨报 / 晚报）
# ---------------------------------------------------------------------------

def build_feedcard(
    articles: list[dict[str, Any]],
    title: str = "AI 日报",
) -> dict[str, Any]:
    """构建 feedCard 消息体.

    Args:
        articles: 文章列表，每篇需包含 title / url / pic_url (可选)
        title: 卡片标题

    Returns:
        完整的钉钉 feedCard 消息体
    """
    links: list[dict[str, str]] = []
    for article in articles:
        link: dict[str, str] = {
            "title": article.get("title_zh", "") or article.get("title", "无标题"),
            "messageURL": article.get("url", ""),
        }
        pic_url = article.get("pic_url", "")
        if pic_url:
            link["picURL"] = pic_url
        links.append(link)

    return {
        "msgtype": "feedCard",
        "feedCard": {
            "links": links,
        },
    }


# ---------------------------------------------------------------------------
# 2.2 actionCard 消息（即时热点）
# ---------------------------------------------------------------------------

def build_actioncard(article: dict[str, Any]) -> dict[str, Any]:
    """构建 actionCard 消息体.

    Args:
        article: 文章数据，需包含 title / summary_zh / url / obsidian_url (可选)

    Returns:
        完整的钉钉 actionCard 消息体
    """
    title = article.get("title_zh", "") or article.get("title", "无标题")
    summary = article.get("summary_zh", "")
    url = article.get("url", "")
    obsidian_url = article.get("obsidian_url", "")

    # 限制摘要长度（actionCard 建议 500 字符）
    if len(summary) > 480:
        summary = summary[:477] + "..."

    markdown_text = f"### {title}\n\n{summary}"

    buttons: list[dict[str, str]] = [
        {
            "title": "阅读原文",
            "actionURL": url,
        },
    ]

    if obsidian_url:
        buttons.append(
            {
                "title": "查看 Obsidian",
                "actionURL": obsidian_url,
            }
        )

    return {
        "msgtype": "actionCard",
        "actionCard": {
            "title": title,
            "text": markdown_text,
            "btnOrientation": "1",
            "btns": buttons,
        },
    }


# ---------------------------------------------------------------------------
# 2.3 周报 markdown 消息
# ---------------------------------------------------------------------------

def build_markdown_weekly(
    stats: dict[str, Any],
    top_articles: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建周报 markdown 消息.

    Args:
        stats: 本周统计数据，包含 total / categories 等
        top_articles: Top 5 热点文章

    Returns:
        完整的钉钉 markdown 消息体
    """
    total = stats.get("total", 0)
    categories = stats.get("categories", {})

    lines: list[str] = [
        "## AI 周报",
        "",
        f"**本周共收录 {total} 篇 AI 相关文章**",
        "",
    ]

    # 分类分布
    if categories:
        lines.append("### 分类分布")
        lines.append("")
        for cat, count in categories.items():
            lines.append(f"- {cat}: {count} 篇")
        lines.append("")

    # Top 5 热点
    if top_articles:
        lines.append("### 热点 TOP 5")
        lines.append("")
        for i, article in enumerate(top_articles, 1):
            title = article.get("title_zh", "") or article.get("title", "无标题")
            url = article.get("url", "")
            score = article.get("trend_score", 0.0)
            lines.append(f"{i}. [{title}]({url}) (热度: {score:.1f})")
        lines.append("")

    markdown_text = "\n".join(lines)

    # 钉钉 markdown 建议 1000 字符
    if len(markdown_text) > 2000:
        markdown_text = markdown_text[:1997] + "..."

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": "AI 周报",
            "text": markdown_text,
        },
    }


# ---------------------------------------------------------------------------
# 2.4 午间速报 markdown 消息
# ---------------------------------------------------------------------------

def build_markdown_noon(articles: list[dict[str, Any]]) -> dict[str, Any]:
    """构建午间速报 markdown 消息.

    Args:
        articles: 热点文章列表（trend_score >= 8）

    Returns:
        完整的钉钉 markdown 消息体
    """
    lines: list[str] = [
        "## 午间速报 - AI 热点",
        "",
    ]

    if not articles:
        lines.append("暂无新增热点。")
    else:
        for article in articles:
            title = article.get("title_zh", "") or article.get("title", "无标题")
            url = article.get("url", "")
            score = article.get("trend_score", 0.0)
            source = article.get("source_name", "")
            lines.append(
                f"- [{title}]({url}) (热度: {score:.1f}) - {source}"
            )

    lines.append("")
    lines.append(f"本次推送 {len(articles)} 条热点")

    markdown_text = "\n".join(lines)

    if len(markdown_text) > 2000:
        markdown_text = markdown_text[:1997] + "..."

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": "午间速报 - AI 热点",
            "text": markdown_text,
        },
    }


# ---------------------------------------------------------------------------
# 2.5 测试消息
# ---------------------------------------------------------------------------

def build_test_message() -> dict[str, Any]:
    """构建测试消息（验证 Webhook 连通性）.

    Returns:
        简单的钉钉 markdown 测试消息体
    """
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": "AI News Tips 测试",
            "text": "## 测试消息\n\n这是一条来自 AI News Tips 的测试消息，用于验证钉钉 Webhook 连通性。",
        },
    }
