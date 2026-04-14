"""BaseFetcher 抽象基类 — 统一采集接口、去重、水印管理、入库."""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from ainews.storage.crud import upsert
from ainews.storage.database import get_session
from ainews.storage.models import Article, FetchLog, SourceMetric

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """所有数据源采集器的抽象基类.

    子类只需实现 fetch_items() 即可获得去重、水印读写、入库等通用能力.
    """

    def __init__(self, source_name: str, config: Any = None) -> None:
        self.source_name = source_name
        self.config = config
        self._session: Session | None = None

    # ------------------------------------------------------------------
    # 抽象方法 — 子类必须实现
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """从数据源拉取原始条目.

        Args:
            since: 上次水印值（时间戳/ETag 等），None 表示全量拉取
            backfill_days: 回填天数（仅部分源支持）

        Returns:
            原始条目列表，每条至少包含 url / title 字段
        """

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def fetch(
        self,
        backfill_days: Optional[int] = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> list[Article]:
        """采集入口 — 加载水印 → 拉取 → 去重 → 入库 → 更新水印."""
        since: Optional[str] = None
        if not force:
            since = self._load_cursor()

        logger.info(
            "[%s] 开始采集 since=%s backfill=%s force=%s dry_run=%s",
            self.source_name,
            since,
            backfill_days,
            force,
            dry_run,
        )

        items = self.fetch_items(since=since, backfill_days=backfill_days)
        logger.info("[%s] 拉取到 %d 条原始条目", self.source_name, len(items))

        if not items:
            return []

        if dry_run:
            logger.info("[%s] dry-run 模式，跳过去重和入库", self.source_name)
            return []

        new_items = self._dedup_by_url(items)
        logger.info("[%s] 去重后 %d 条新条目", self.source_name, len(new_items))

        articles = self._save_articles(new_items)

        # 子类可覆写以返回自定义 cursor
        cursor = self._build_cursor(items)
        self._update_cursor(cursor, len(articles))

        logger.info("[%s] 入库 %d 条文章", self.source_name, len(articles))
        return articles

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """测试数据源连通性.

        Returns:
            {"ok": True, "latency_ms": 120, "detail": "..."} 或
            {"ok": False, "error": "..."}
        """

    # ------------------------------------------------------------------
    # 水印管理
    # ------------------------------------------------------------------

    def _load_cursor(self) -> Optional[str]:
        """从 fetch_log 读取上次采集水印."""
        with self._get_session() as session:
            log = session.exec(
                select(FetchLog).where(FetchLog.source == self.source_name)
            ).first()
            if log is not None:
                logger.debug("[%s] 读取水印: %s", self.source_name, log.cursor)
                return log.cursor or None
            logger.info("[%s] 无历史水印，将全量拉取", self.source_name)
            return None

    def _update_cursor(self, cursor: Optional[str], items_fetched: int) -> None:
        """更新 fetch_log 水印."""
        now = datetime.now()
        with self._get_session() as session:
            upsert(
                session,
                model=FetchLog,
                filters={"source": self.source_name},
                updates={
                    "cursor": cursor or "",
                    "last_fetch_at": now,
                    "items_fetched": items_fetched,
                    "updated_at": now,
                },
            )
            session.commit()
        logger.debug("[%s] 水印已更新: cursor=%s count=%d", self.source_name, cursor, items_fetched)

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """从拉取到的条目构建新水印. 子类可覆写."""
        if not items:
            return None
        # 默认取最大的 published_at 或 time
        timestamps = []
        for item in items:
            t = item.get("published_at") or item.get("time")
            if t is not None:
                if isinstance(t, datetime):
                    timestamps.append(t.isoformat())
                else:
                    timestamps.append(str(t))
        if timestamps:
            return max(timestamps)
        return None

    # ------------------------------------------------------------------
    # URL 去重
    # ------------------------------------------------------------------

    @staticmethod
    def _url_hash(url: str) -> str:
        """计算 URL 的 SHA256 哈希."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _dedup_by_url(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """过滤已有 URL，返回新条目列表."""
        if not items:
            return []

        url_hashes = {self._url_hash(item["url"]) for item in items if item.get("url")}

        with self._get_session() as session:
            existing_hashes: set[str] = set()
            if url_hashes:
                # 分批查询避免 SQL 参数过多
                batch_size = 500
                hash_list = list(url_hashes)
                for i in range(0, len(hash_list), batch_size):
                    batch = hash_list[i : i + batch_size]
                    rows = session.exec(
                        select(Article.url_hash).where(Article.url_hash.in_(batch))
                    ).all()
                    existing_hashes.update(rows)

        new_items = [
            item for item in items
            if item.get("url") and self._url_hash(item["url"]) not in existing_hashes
        ]

        skipped = len(items) - len(new_items)
        if skipped > 0:
            logger.info("[%s] 跳过 %d 条已存在 URL", self.source_name, skipped)

        return new_items

    # ------------------------------------------------------------------
    # 批量入库
    # ------------------------------------------------------------------

    def _save_articles(self, items: list[dict[str, Any]]) -> list[Article]:
        """将去重后的条目逐条写入 articles 表，跳过已存在的 URL."""
        if not items:
            return []

        now = datetime.now()
        articles: list[Article] = []

        with self._get_session() as session:
            for item in items:
                url = item["url"]
                url_hash = self._url_hash(url)

                # 检查是否已存在（防御竞态）
                existing = session.exec(
                    select(Article).where(Article.url_hash == url_hash)
                ).first()
                if existing is not None:
                    logger.debug("[%s] 跳过已存在 URL: %s", self.source_name, url)
                    continue

                article = Article(
                    url=url,
                    url_hash=url_hash,
                    title=item.get("title", ""),
                    content_raw=item.get("content_raw", ""),
                    source=item.get("source", self.source_name),
                    source_name=item.get("source_name", ""),
                    author=item.get("author", ""),
                    category=item.get("category", ""),
                    status="unread",
                    processed=False,
                    published_at=item.get("published_at"),
                    fetched_at=now,
                    imported_at=now,
                )
                session.add(article)
                session.flush()  # 逐条 flush 以获取 id 并捕获单条冲突

                articles.append(article)

                # 写入 source_metrics
                metrics = item.get("metrics")
                if metrics and article.id is not None:
                    metric = SourceMetric(
                        article_id=article.id,
                        source=self.source_name,
                        platform_score=metrics.get("platform_score", 0.0),
                        comment_count=metrics.get("comment_count", 0),
                        upvote_count=metrics.get("upvote_count", 0),
                        fetched_at=now,
                    )
                    session.add(metric)

            session.commit()

            # 使对象与 session 分离但保留已加载的属性
            session.expunge_all()

        return articles

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _get_session(self) -> Any:
        """获取数据库 Session 上下文管理器."""
        from ainews.storage.database import get_session as _get_session
        return _get_session()
