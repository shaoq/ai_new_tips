"""RSS/Atom 采集器 — feedparser 解析, ETag/Last-Modified 增量."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import feedparser
import httpx

from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

# 每个 RSS 源最大拉取条目数（防止首次全量拉取过多）
MAX_ENTRIES_PER_FEED = 30

# 默认 RSS 源列表
DEFAULT_RSS_FEEDS: dict[str, str] = {
    "openai-blog": "https://openai.com/blog/rss.xml",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    "marktechpost": "https://www.marktechpost.com/feed/",
    "venturebeat-ai": "https://venturebeat.com/category/ai/feed/",
    # Reddit RSS（无需 OAuth，替代 PRAW 采集器）
    "reddit-machinelearning": "https://www.reddit.com/r/MachineLearning/.rss",
    "reddit-localllama": "https://www.reddit.com/r/LocalLLaMA/.rss",
    "reddit-chatgpt": "https://www.reddit.com/r/ChatGPT/.rss",
}


class RSSFetcher(BaseFetcher):
    """RSS/Atom 采集器.

    支持多源管理、ETag/Last-Modified 增量、降级时间水印.
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="rss", config=config)
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "ai-news-tips/1.0"},
        )
        self.feeds: dict[str, str] = dict(DEFAULT_RSS_FEEDS)
        if config and hasattr(config, "rss_feeds"):
            custom_feeds = getattr(config, "rss_feeds", None)
            if custom_feeds and isinstance(custom_feeds, dict):
                self.feeds.update(custom_feeds)

    # ------------------------------------------------------------------
    # fetch_items — 遍历所有 RSS 源
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """采集所有 RSS 源."""
        all_items: list[dict[str, Any]] = []

        for feed_name, feed_url in self.feeds.items():
            try:
                items = self._fetch_feed(feed_name, feed_url, since=since)
                all_items.extend(items)
            except Exception:
                logger.error(
                    "[rss] 采集 %s (%s) 失败", feed_name, feed_url, exc_info=True
                )

        return all_items

    def _fetch_feed(
        self,
        feed_name: str,
        feed_url: str,
        since: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """采集单个 RSS 源."""
        # 解析已有水印
        etag: Optional[str] = None
        last_modified: Optional[str] = None
        last_item_ts: Optional[datetime] = None

        if since:
            try:
                cursor_data = json.loads(since)
                etag = cursor_data.get("etag")
                last_modified = cursor_data.get("last_modified")
                ts_str = cursor_data.get("last_item_timestamp")
                if ts_str:
                    last_item_ts = datetime.fromisoformat(ts_str)
            except (json.JSONDecodeError, ValueError, TypeError):
                # 如果 cursor 不是 JSON，当作时间水印
                pass

        # 先用 httpx 获取内容，处理重定向和非标准 XML
        try:
            headers: dict[str, str] = {}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified

            resp = self._client.get(feed_url, headers=headers)
            if resp.status_code == 304:
                logger.info("[rss:%s] 304 Not Modified，无新内容", feed_name)
                return []
            resp.raise_for_status()
            content = resp.text
        except Exception as exc:
            logger.warning("[rss:%s] HTTP 获取失败: %s", feed_name, exc)
            # 降级：让 feedparser 直接请求
            content = None

        # 使用 feedparser 解析
        if content is not None:
            feed: Any = feedparser.parse(content)
        else:
            feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning("[rss:%s] 解析异常: %s", feed_name, feed.bozo_exception)
            return []

        items: list[dict[str, Any]] = []
        for entry in feed.entries:
            if len(items) >= MAX_ENTRIES_PER_FEED:
                logger.info("[rss:%s] 达到单源上限 %d 条，截断", feed_name, MAX_ENTRIES_PER_FEED)
                break

            url = getattr(entry, "link", None) or getattr(entry, "href", None)
            if not url:
                continue

            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            author = getattr(entry, "author", "")

            # 发布时间
            published_at = self._parse_entry_date(entry)

            # 降级：基于发布时间过滤
            if last_item_ts and published_at:
                pub_aware = published_at.replace(tzinfo=timezone.utc) if published_at.tzinfo is None else published_at
                if pub_aware <= last_item_ts:
                    continue

            items.append({
                "url": url,
                "title": title,
                "content_raw": summary,
                "source": "rss",
                "source_name": feed_name,
                "author": author,
                "published_at": published_at,
            })

        logger.info("[rss:%s] 获取 %d 条新条目", feed_name, len(items))
        return items

    # ------------------------------------------------------------------
    # 日期解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_entry_date(entry: Any) -> Optional[datetime]:
        """从 feed entry 提取发布时间."""
        for attr in ("published_parsed", "updated_parsed"):
            time_struct = getattr(entry, attr, None)
            if time_struct:
                try:
                    import time as _time
                    return datetime(
                        *time_struct[:6],
                        tzinfo=timezone.utc,
                    )
                except (TypeError, ValueError):
                    continue

        # 尝试字符串格式
        for attr in ("published", "updated"):
            date_str = getattr(entry, attr, None)
            if date_str and isinstance(date_str, str):
                try:
                    from email.utils import parsedate_to_datetime
                    return parsedate_to_datetime(date_str)
                except (ValueError, TypeError):
                    pass

        return None

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """构建 RSS 水印: etag + last_modified + last_item_timestamp."""
        cursor_data: dict[str, str] = {}

        # 从最近的 feed 中提取 etag/last_modified
        # 注意：feedparser 的 etag/modified 在 feed 对象上，不在 items 上
        # 这里我们用 last_item_timestamp 作为主要水印
        if items:
            dates: list[datetime] = []
            for item in items:
                pub = item.get("published_at")
                if isinstance(pub, datetime):
                    dates.append(pub)
            if dates:
                cursor_data["last_item_timestamp"] = max(dates).isoformat()

        if cursor_data:
            return json.dumps(cursor_data)
        return None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试第一个 RSS 源连通性."""
        feed_name, feed_url = next(iter(self.feeds.items()), ("none", ""))
        if not feed_url:
            return {"ok": False, "error": "无 RSS 源配置"}

        import time as _time
        start = _time.monotonic()
        try:
            feed = feedparser.parse(feed_url)
            latency = int((_time.monotonic() - start) * 1000)
            if feed.bozo and not feed.entries:
                return {"ok": False, "error": f"解析失败: {feed.bozo_exception}"}
            if feed.entries:
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "detail": f"[{feed_name}] 连接成功，{len(feed.entries)} 条条目",
                }
            return {
                "ok": True,
                "latency_ms": latency,
                "detail": f"[{feed_name}] 连接成功，但无条目",
            }
        except Exception as e:
            return {"ok": False, "error": f"[{feed_name}] {e}"}

    def test_feed(self, feed_url: str) -> dict[str, Any]:
        """测试指定 RSS URL 连通性."""
        import time as _time
        start = _time.monotonic()
        try:
            feed = feedparser.parse(feed_url)
            latency = int((_time.monotonic() - start) * 1000)
            if feed.bozo and not feed.entries:
                return {"ok": False, "error": f"解析失败: {feed.bozo_exception}"}
            return {
                "ok": True,
                "latency_ms": latency,
                "detail": f"连接成功，{len(feed.entries)} 条条目",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
