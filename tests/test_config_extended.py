"""测试配置扩展 — RedditConfig、HFPapersConfig、GitHubConfig、ChineseConfig."""

from __future__ import annotations

import pytest

from ainews.config.settings import (
    AppConfig,
    ChineseConfig,
    ChineseSourceConfig,
    GitHubConfig,
    HFPapersConfig,
    RedditConfig,
    SourcesConfig,
)


class TestRedditConfig:
    def test_defaults(self) -> None:
        cfg = RedditConfig()
        assert cfg.enabled is True
        assert cfg.client_id == ""
        assert cfg.client_secret == ""
        assert cfg.user_agent == "ai-news-tips/1.0"
        assert cfg.subreddits == ["MachineLearning", "LocalLLaMA", "ChatGPT"]
        assert cfg.fetch_interval_minutes == 30

    def test_custom_values(self) -> None:
        cfg = RedditConfig(
            client_id="test_id",
            client_secret="test_secret",
            subreddits=["test"],
            fetch_interval_minutes=60,
        )
        assert cfg.client_id == "test_id"
        assert cfg.subreddits == ["test"]
        assert cfg.fetch_interval_minutes == 60


class TestHFPapersConfig:
    def test_defaults(self) -> None:
        cfg = HFPapersConfig()
        assert cfg.enabled is True
        assert cfg.fetch_interval_minutes == 360
        assert cfg.min_upvotes == 10

    def test_custom_min_upvotes(self) -> None:
        cfg = HFPapersConfig(min_upvotes=50)
        assert cfg.min_upvotes == 50


class TestGitHubConfig:
    def test_defaults(self) -> None:
        cfg = GitHubConfig()
        assert cfg.enabled is True
        assert cfg.token == ""
        assert "machine-learning" in cfg.topics
        assert "python" in cfg.languages
        assert cfg.min_stars == 50
        assert cfg.fetch_interval_minutes == 360

    def test_custom_topics(self) -> None:
        cfg = GitHubConfig(topics=["deep-learning", "nlp"])
        assert cfg.topics == ["deep-learning", "nlp"]


class TestChineseConfig:
    def test_defaults(self) -> None:
        cfg = ChineseConfig()
        assert cfg.enabled is True
        assert cfg.sources == []
        assert cfg.fetch_interval_minutes == 60

    def test_chinese_source_config_valid(self) -> None:
        cfg = ChineseSourceConfig(name="qbitai", url="https://www.qbitai.com/", method="rss")
        assert cfg.name == "qbitai"
        assert cfg.method == "rss"

    def test_chinese_source_config_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="method 必须是 rss 或 scrape"):
            ChineseSourceConfig(name="test", url="http://test.com", method="invalid")

    def test_chinese_with_sources(self) -> None:
        sources = [
            ChineseSourceConfig(name="qbitai", url="https://www.qbitai.com/", method="rss"),
            ChineseSourceConfig(name="aibase", url="https://www.aibase.com/", method="scrape"),
        ]
        cfg = ChineseConfig(sources=sources)
        assert len(cfg.sources) == 2
        assert cfg.sources[0].name == "qbitai"
        assert cfg.sources[1].method == "scrape"


class TestSourcesConfig:
    def test_all_sources_present(self) -> None:
        cfg = SourcesConfig()
        assert hasattr(cfg, "hackernews")
        assert hasattr(cfg, "arxiv")
        assert hasattr(cfg, "reddit")
        assert hasattr(cfg, "hf_papers")
        assert hasattr(cfg, "github")
        assert hasattr(cfg, "chinese")
        assert hasattr(cfg, "rss")

    def test_reddit_is_reddit_config(self) -> None:
        cfg = SourcesConfig()
        assert isinstance(cfg.reddit, RedditConfig)

    def test_hf_papers_is_hf_papers_config(self) -> None:
        cfg = SourcesConfig()
        assert isinstance(cfg.hf_papers, HFPapersConfig)

    def test_github_is_github_config(self) -> None:
        cfg = SourcesConfig()
        assert isinstance(cfg.github, GitHubConfig)

    def test_chinese_is_chinese_config(self) -> None:
        cfg = SourcesConfig()
        assert isinstance(cfg.chinese, ChineseConfig)


class TestAppConfigMaskSecrets:
    def test_mask_reddit_secret(self) -> None:
        config = AppConfig(
            sources=SourcesConfig(
                reddit=RedditConfig(client_secret="my_super_secret_key"),
            ),
        )
        masked = config.mask_secrets()
        assert masked.sources.reddit.client_secret != "my_super_secret_key"
        assert "***" in masked.sources.reddit.client_secret
        # Original unchanged
        assert config.sources.reddit.client_secret == "my_super_secret_key"

    def test_mask_github_token(self) -> None:
        config = AppConfig(
            sources=SourcesConfig(
                github=GitHubConfig(token="ghp_abc123def456"),
            ),
        )
        masked = config.mask_secrets()
        assert masked.sources.github.token != "ghp_abc123def456"
        assert "***" in masked.sources.github.token

    def test_config_serialization_roundtrip(self) -> None:
        """配置序列化/反序列化保持一致."""
        config = AppConfig(
            sources=SourcesConfig(
                reddit=RedditConfig(
                    client_id="test_id",
                    subreddits=["MachineLearning", "LocalLLaMA"],
                ),
                hf_papers=HFPapersConfig(min_upvotes=20),
                github=GitHubConfig(topics=["ai", "llm"], min_stars=100),
                chinese=ChineseConfig(
                    sources=[
                        ChineseSourceConfig(name="qbitai", url="https://qbitai.com", method="rss"),
                    ],
                ),
            ),
        )
        data = config.model_dump()
        restored = AppConfig(**data)

        assert restored.sources.reddit.client_id == "test_id"
        assert restored.sources.reddit.subreddits == ["MachineLearning", "LocalLLaMA"]
        assert restored.sources.hf_papers.min_upvotes == 20
        assert restored.sources.github.topics == ["ai", "llm"]
        assert restored.sources.github.min_stars == 100
        assert len(restored.sources.chinese.sources) == 1
        assert restored.sources.chinese.sources[0].name == "qbitai"
