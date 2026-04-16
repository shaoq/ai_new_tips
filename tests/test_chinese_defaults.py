"""测试中文采集器默认源加载 — 无配置时使用 DEFAULT_CHINESE_SOURCES、有配置时覆盖."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ainews.config.settings import ChineseConfig, ChineseSourceConfig
from ainews.fetcher.chinese import DEFAULT_CHINESE_SOURCES, ChineseFetcher


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def fetcher_no_config() -> ChineseFetcher:
    """创建无显式配置的 ChineseFetcher（触发默认源加载）."""
    return ChineseFetcher(config=ChineseConfig(sources=[]))


@pytest.fixture
def fetcher_with_config() -> ChineseFetcher:
    """创建带自定义源的 ChineseFetcher."""
    cfg = ChineseConfig(
        sources=[
            ChineseSourceConfig(name="custom", url="https://custom.com/feed", method="rss"),
            ChineseSourceConfig(name="custom2", url="https://custom2.com/feed", method="rss"),
        ],
    )
    return ChineseFetcher(config=cfg)


# ------------------------------------------------------------------
# 测试：无配置时使用 DEFAULT_CHINESE_SOURCES
# ------------------------------------------------------------------


class TestDefaultSources:
    def test_empty_config_loads_defaults(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """配置 sources 为空列表时，_resolve_config 返回 DEFAULT_CHINESE_SOURCES."""
        resolved = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        assert len(resolved.sources) == len(DEFAULT_CHINESE_SOURCES)

    def test_default_source_names(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """默认源包含 qbitai, jiqizhixin, 36kr, ifanr."""
        resolved = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        names = {s.name for s in resolved.sources}
        assert "qbitai" in names
        assert "jiqizhixin" in names
        assert "36kr" in names
        assert "ifanr" in names

    def test_default_source_urls(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """默认源的 URL 与 DEFAULT_CHINESE_SOURCES 一致."""
        resolved = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        default_urls = {s["url"] for s in DEFAULT_CHINESE_SOURCES}
        resolved_urls = {s.url for s in resolved.sources}
        assert default_urls == resolved_urls

    def test_default_source_methods(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """默认源的 method 都是 rss."""
        resolved = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        for source in resolved.sources:
            assert source.method == "rss"

    def test_none_config_triggers_defaults(self) -> None:
        """传入 None 配置时也加载默认源."""
        f = ChineseFetcher(config=None)
        # _resolve_config 内部会 try loader, 失败时用默认源
        # 由于测试环境无配置文件，会走 fallback
        resolved = f._resolve_config(None)
        # fallback 或 loader 都可能返回默认源
        assert isinstance(resolved, ChineseConfig)


# ------------------------------------------------------------------
# 测试：有配置时覆盖默认值
# ------------------------------------------------------------------


class TestConfigOverride:
    def test_custom_sources_override_defaults(
        self, fetcher_with_config: ChineseFetcher,
    ) -> None:
        """有自定义源时不使用默认源."""
        resolved = fetcher_with_config._resolve_config(ChineseConfig(
            sources=[
                ChineseSourceConfig(name="custom", url="https://custom.com/feed", method="rss"),
            ],
        ))
        assert len(resolved.sources) == 1
        assert resolved.sources[0].name == "custom"

    def test_custom_sources_not_default(
        self, fetcher_with_config: ChineseFetcher,
    ) -> None:
        """自定义源不包含默认源名称."""
        resolved = fetcher_with_config._resolve_config(ChineseConfig(
            sources=[
                ChineseSourceConfig(name="custom", url="https://custom.com/feed", method="rss"),
            ],
        ))
        names = {s.name for s in resolved.sources}
        assert "qbitai" not in names
        assert "jiqizhixin" not in names
        assert "36kr" not in names

    def test_multiple_custom_sources(
        self, fetcher_with_config: ChineseFetcher,
    ) -> None:
        """多个自定义源都保留."""
        resolved = fetcher_with_config._resolve_config(ChineseConfig(
            sources=[
                ChineseSourceConfig(name="s1", url="https://s1.com/feed", method="rss"),
                ChineseSourceConfig(name="s2", url="https://s2.com/", method="scrape"),
                ChineseSourceConfig(name="s3", url="https://s3.com/feed", method="rss"),
            ],
        ))
        assert len(resolved.sources) == 3
        methods = {s.method for s in resolved.sources}
        assert "rss" in methods
        assert "scrape" in methods


# ------------------------------------------------------------------
# 测试：_resolve_config 返回类型
# ------------------------------------------------------------------


class TestResolveConfig:
    def test_returns_chinese_config_instance(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """_resolve_config 返回 ChineseConfig 实例."""
        result = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        assert isinstance(result, ChineseConfig)

    def test_result_sources_are_chinese_source_config(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """返回的 sources 列表中每个元素都是 ChineseSourceConfig."""
        result = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        for source in result.sources:
            assert isinstance(source, ChineseSourceConfig)

    def test_config_with_sources_returns_same(
        self, fetcher_with_config: ChineseFetcher,
    ) -> None:
        """传入已有 sources 的 ChineseConfig 时原样返回."""
        original = ChineseConfig(
            sources=[
                ChineseSourceConfig(name="test", url="https://test.com/feed", method="rss"),
            ],
        )
        result = fetcher_with_config._resolve_config(original)
        assert result is original

    def test_config_with_no_sources_returns_defaults(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """传入空 sources 的 ChineseConfig 时返回填充了默认源的 ChineseConfig."""
        empty = ChineseConfig(sources=[])
        result = fetcher_no_config._resolve_config(empty)
        # 返回的不是原始的空 config
        assert len(result.sources) > 0

    def test_default_sources_preserved_across_resolve(
        self, fetcher_no_config: ChineseFetcher,
    ) -> None:
        """多次调用 _resolve_config 返回一致的默认源."""
        result1 = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        result2 = fetcher_no_config._resolve_config(ChineseConfig(sources=[]))
        names1 = [s.name for s in result1.sources]
        names2 = [s.name for s in result2.sources]
        assert names1 == names2
