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
# source → domain (用于 Google Favicon API)
# ---------------------------------------------------------------------------

_SOURCE_DOMAIN_MAP: dict[str, str] = {
    "hackernews": "news.ycombinator.com",
    "reddit": "www.reddit.com",
    "rss": "www.google.com",  # RSS 来源多样，用通用兜底
    "chinese": "www.jiqizhixin.com",  # 中文源默认机器之心
    "twitter": "x.com",
    "arxiv": "arxiv.org",
    "hf_papers": "huggingface.co",
    "github": "github.com",
    "github-releases": "github.com",
}

_FAVICON_TEMPLATE = "https://www.google.com/s2/favicons?domain={domain}&sz=64"
_FALLBACK_DOMAIN = "www.google.com"


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
        favicon 图片 URL (Google Favicon API)
    """
    domain = _SOURCE_DOMAIN_MAP.get(source, _FALLBACK_DOMAIN)
    return _FAVICON_TEMPLATE.format(domain=domain)
