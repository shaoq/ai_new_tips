"""Source type and favicon URL mapping for push messages."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# source → source_type 映射
# ---------------------------------------------------------------------------

_SOURCE_TYPE_MAP: dict[str, str] = {
    "hackernews": "article",
    "reddit": "article",
    "rss": "article",
    "chinese": "article",
    "twitter": "article",
    "arxiv": "paper",
    "hf_papers": "paper",
    "github": "repo",
    "github-releases": "repo",
}

# ---------------------------------------------------------------------------
# source_type → 中文展示标签
# ---------------------------------------------------------------------------

_SOURCE_TYPE_LABEL: dict[str, str] = {
    "article": "文章",
    "paper": "论文",
    "repo": "仓库",
}

# ---------------------------------------------------------------------------
# source → favicon URL（直接映射，避免依赖被墙的 Google Favicon API）
# ---------------------------------------------------------------------------

_SOURCE_FAVICON_MAP: dict[str, str] = {
    # 可达源 → 自身 favicon
    "hackernews": "https://news.ycombinator.com/favicon.ico",
    "arxiv": "https://arxiv.org/favicon.ico",
    "hf_papers": "https://huggingface.co/favicon.ico",
    "github": "https://github.com/favicon.ico",
    "github-releases": "https://github.com/favicon.ico",
    "rss": "https://venturebeat.com/favicon.ico",
    "chinese": "https://www.jiqizhixin.com/favicon.ico",
    # 被墙源 → flaticon CDN 图标
    "reddit": "https://cdn-icons-png.flaticon.com/128/2111/2111620.png",
    "twitter": "https://cdn-icons-png.flaticon.com/128/5968/5968819.png",
}

_FALLBACK_FAVICON = "https://venturebeat.com/favicon.ico"


def get_source_type(source: str) -> str:
    """将 source 映射为推送展示用的来源类型.

    Args:
        source: 数据源标识符 (e.g. "github", "arxiv")

    Returns:
        source_type: "article" / "paper" / "repo"
    """
    return _SOURCE_TYPE_MAP.get(source, "article")


def get_source_type_label(source_type: str) -> str:
    """获取 source_type 的中文展示标签.

    Args:
        source_type: 来源类型 ("article" / "paper" / "repo")

    Returns:
        中文标签，如 "文章"、"论文"、"仓库"
    """
    return _SOURCE_TYPE_LABEL.get(source_type, "文章")


def get_favicon_url(source: str) -> str:
    """获取 source 对应的 favicon 图片 URL.

    Args:
        source: 数据源标识符

    Returns:
        favicon 图片 URL（国内可达）
    """
    return _SOURCE_FAVICON_MAP.get(source, _FALLBACK_FAVICON)
