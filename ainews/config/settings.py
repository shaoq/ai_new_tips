"""配置管理：pydantic-settings 配置模型."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class LLMConfig(BaseModel):
    """LLM 配置."""

    base_url: str = "https://api.anthropic.com"
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            msg = f"base_url 必须以 http:// 或 https:// 开头: {v}"
            raise ValueError(msg)
        return v.rstrip("/")

    @field_validator("api_key")
    @classmethod
    def validate_api_key_not_empty_on_access(cls, v: str) -> str:
        return v


class ObsidianConfig(BaseModel):
    """Obsidian 配置."""

    vault_path: str = ""
    api_key: str = ""
    port: int = 27124

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            msg = f"port 必须在 1-65535 范围内: {v}"
            raise ValueError(msg)
        return v


class DingTalkConfig(BaseModel):
    """钉钉配置."""

    webhook_url: str = ""
    secret: str = ""


class SourceConfig(BaseModel):
    """单个数据源配置."""

    enabled: bool = True
    keywords: list[str] = []


class RedditConfig(BaseModel):
    """Reddit 数据源配置."""

    enabled: bool = True
    client_id: str = ""
    client_secret: str = ""
    user_agent: str = "ai-news-tips/1.0"
    subreddits: list[str] = ["MachineLearning", "LocalLLaMA", "ChatGPT"]
    fetch_interval_minutes: int = 30


class HFPapersConfig(BaseModel):
    """HuggingFace Daily Papers 配置."""

    enabled: bool = True
    fetch_interval_minutes: int = 360
    min_upvotes: int = 10


class GitHubConfig(BaseModel):
    """GitHub Trending 配置."""

    enabled: bool = True
    token: str = ""
    topics: list[str] = ["machine-learning", "llm", "ai", "transformer"]
    languages: list[str] = ["python", "typescript"]
    min_stars: int = 50
    fetch_interval_minutes: int = 360


class ChineseSourceConfig(BaseModel):
    """单个中文源配置."""

    name: str = ""
    url: str = ""
    method: str = "rss"  # rss or scrape

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v not in ("rss", "scrape"):
            msg = f"method 必须是 rss 或 scrape: {v}"
            raise ValueError(msg)
        return v


class ChineseConfig(BaseModel):
    """中文数据源配置."""

    enabled: bool = True
    sources: list[ChineseSourceConfig] = []
    fetch_interval_minutes: int = 60


class TwitterConfig(BaseModel):
    """X/Twitter 数据源配置（基于 SocialData.tools API）."""

    enabled: bool = True
    api_key: str = ""
    accounts: list[str] = [
        "karpathy", "ylecun", "AndrewYNg", "rasbt", "ilyasut",
        "sama", "demishassabis", "ClementDelangue", "arthur_mensch",
        "GaryMarcus", "emollick", "CadeMetz", "mattturck",
        "OpenAI", "DeepMind", "AnthropicAI", "huggingface",
    ]
    search_queries: list[str] = []
    min_engagement: int = 100
    fetch_interval_minutes: int = 30


class SourcesConfig(BaseModel):
    """数据源配置集合."""

    hackernews: SourceConfig = SourceConfig(
        enabled=True, keywords=["AI", "LLM", "GPT", "Claude", "Gemini"]
    )
    arxiv: SourceConfig = SourceConfig(
        enabled=True, keywords=["cs.AI", "cs.LG", "cs.CL"]
    )
    reddit: RedditConfig = RedditConfig()
    hf_papers: HFPapersConfig = HFPapersConfig()
    github: GitHubConfig = GitHubConfig()
    chinese: ChineseConfig = ChineseConfig()
    rss: SourceConfig = SourceConfig(
        enabled=True,
        keywords=["OpenAI Blog", "DeepMind", "Anthropic", "Meta AI", "HuggingFace Blog"],
    )
    twitter: TwitterConfig = TwitterConfig()


class LoggingConfig(BaseModel):
    """日志配置."""

    level: str = "INFO"
    path: str = ""

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            msg = f"level 必须是 {valid} 之一: {v}"
            raise ValueError(msg)
        return upper


class AppConfig(BaseModel):
    """应用总配置."""

    llm: LLMConfig = LLMConfig()
    obsidian: ObsidianConfig = ObsidianConfig()
    dingtalk: DingTalkConfig = DingTalkConfig()
    sources: SourcesConfig = SourcesConfig()
    logging: LoggingConfig = LoggingConfig()

    @property
    def config_dir(self) -> Path:
        return Path.home() / ".ainews"

    @property
    def config_path(self) -> Path:
        return self.config_dir / "config.yaml"

    @property
    def db_path(self) -> Path:
        return self.config_dir / "data.db"

    @property
    def log_dir(self) -> Path:
        return self.config_dir / "logs"

    def mask_secrets(self) -> AppConfig:
        """返回敏感字段脱敏后的副本."""
        data = self.model_dump()
        data["llm"]["api_key"] = _mask(data["llm"]["api_key"])
        data["obsidian"]["api_key"] = _mask(data["obsidian"]["api_key"])
        data["dingtalk"]["secret"] = _mask(data["dingtalk"]["secret"])
        data["sources"]["reddit"]["client_secret"] = _mask(
            data["sources"]["reddit"]["client_secret"]
        )
        data["sources"]["github"]["token"] = _mask(
            data["sources"]["github"]["token"]
        )
        data["sources"]["twitter"]["api_key"] = _mask(
            data["sources"]["twitter"]["api_key"]
        )
        return AppConfig(**data)


def _mask(value: str) -> str:
    """脱敏：显示为 ***xxx（仅保留后4位）."""
    if not value or len(value) < 4:
        return "***" if value else ""
    return f"***{value[-4:]}"
