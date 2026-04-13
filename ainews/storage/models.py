"""SQLModel 数据模型."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Article(SQLModel, table=True):
    """文章表."""

    __tablename__ = "articles"

    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    url_hash: str = Field(default="", index=True)
    title: str = Field(default="")
    content_raw: str = Field(default="")
    source: str = Field(default="", index=True)
    source_name: str = Field(default="")
    author: str = Field(default="")
    category: str = Field(default="", index=True)
    summary_zh: str = Field(default="")
    relevance: float = Field(default=0.0)
    tags: str = Field(default="[]")  # JSON array
    entities: str = Field(default="[]")  # JSON array
    trend_score: float = Field(default=0.0, index=True)
    is_trending: bool = Field(default=False)
    platforms: str = Field(default="[]")  # JSON array
    status: str = Field(default="unread", index=True)
    processed: bool = Field(default=False)
    dingtalk_sent: bool = Field(default=False)
    obsidian_synced: bool = Field(default=False)
    published_at: Optional[datetime] = Field(default=None)
    fetched_at: Optional[datetime] = Field(default=None, index=True)
    imported_at: Optional[datetime] = Field(default=None)
    obsidian_path: str = Field(default="")


class SourceMetric(SQLModel, table=True):
    """源指标表."""

    __tablename__ = "source_metrics"

    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="articles.id")
    source: str = Field(default="")
    platform_score: float = Field(default=0.0)
    comment_count: int = Field(default=0)
    upvote_count: int = Field(default=0)
    velocity: float = Field(default=0.0)
    fetched_at: Optional[datetime] = Field(default=None)


class FetchLog(SQLModel, table=True):
    """拉取日志表（增量水印）."""

    __tablename__ = "fetch_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(unique=True)
    last_fetch_at: Optional[datetime] = Field(default=None)
    cursor: str = Field(default="")
    items_fetched: int = Field(default=0)
    updated_at: Optional[datetime] = Field(default=None)


class Entity(SQLModel, table=True):
    """命名实体表."""

    __tablename__ = "entities"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    type: str = Field(default="")  # person/company/project/technology
    first_seen_at: Optional[datetime] = Field(default=None)
    mention_count: int = Field(default=0)
    is_new: bool = Field(default=True)
    meta_json: str = Field(default="{}")  # JSON


class ArticleEntity(SQLModel, table=True):
    """文章-实体关联表."""

    __tablename__ = "article_entities"

    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="articles.id")
    entity_id: int = Field(foreign_key="entities.id")


class Cluster(SQLModel, table=True):
    """文章聚类表."""

    __tablename__ = "clusters"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic: str = Field(default="")
    article_ids: str = Field(default="[]")  # JSON array
    source_count: int = Field(default=0)
    trend_score: float = Field(default=0.0)
    created_at: Optional[datetime] = Field(default=None)


class PushLog(SQLModel, table=True):
    """推送日志表."""

    __tablename__ = "push_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="articles.id")
    push_type: str = Field(default="")  # feedcard/actioncard/markdown/weekly
    msg_id: str = Field(default="")
    pushed_at: Optional[datetime] = Field(default=None)
