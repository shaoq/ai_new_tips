"""Fetcher 注册表 — 维护 source_name → FetcherClass 映射."""

from __future__ import annotations

from typing import Any

from ainews.fetcher.base import BaseFetcher

_registry: dict[str, type[BaseFetcher]] = {}


def register(name: str, fetcher_cls: type[BaseFetcher]) -> None:
    """注册采集器类."""
    _registry[name] = fetcher_cls


def get_fetcher(name: str, config: Any = None) -> BaseFetcher:
    """获取采集器实例."""
    # 延迟注册（首次调用时）
    _ensure_registered()

    cls = _registry.get(name)
    if cls is None:
        available = ", ".join(sorted(_registry.keys()))
        msg = f"未知数据源: {name}。可用源: {available}"
        raise KeyError(msg)
    return cls(config=config)


def list_sources() -> list[str]:
    """列出所有已注册的数据源名称."""
    _ensure_registered()
    return sorted(_registry.keys())


def is_registered(name: str) -> bool:
    """检查数据源是否已注册."""
    _ensure_registered()
    return name in _registry


_registered = False


def _ensure_registered() -> None:
    """确保内置采集器已注册（延迟导入避免循环依赖）."""
    global _registered
    if _registered:
        return
    _registered = True

    from ainews.fetcher.hackernews import HackerNewsFetcher
    from ainews.fetcher.arxiv import ArXivFetcher
    from ainews.fetcher.rss import RSSFetcher
    from ainews.fetcher.reddit import RedditFetcher
    from ainews.fetcher.hf_papers import HFPapersFetcher
    from ainews.fetcher.github import GitHubFetcher
    from ainews.fetcher.chinese import ChineseFetcher

    register("hackernews", HackerNewsFetcher)
    register("arxiv", ArXivFetcher)
    register("rss", RSSFetcher)
    register("reddit", RedditFetcher)
    register("hf_papers", HFPapersFetcher)
    register("github", GitHubFetcher)
    register("chinese", ChineseFetcher)
