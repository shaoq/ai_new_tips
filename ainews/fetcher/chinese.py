"""中文 AI 媒体采集器 — RSS + 网页解析."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

from ainews.config.settings import ChineseConfig, ChineseSourceConfig
from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

# 中文源专属 CSS 选择器
# 默认中文 AI 媒体源
DEFAULT_CHINESE_SOURCES: list[dict[str, str]] = [
    {"name": "qbitai", "url": "https://www.qbitai.com/feed", "method": "rss"},
    {"name": "jiqizhixin", "url": "https://www.jiqizhixin.com/rss", "method": "rss"},
    {"name": "36kr", "url": "https://www.36kr.com/feed", "method": "rss"},
    {"name": "ifanr", "url": "https://www.ifanr.com/feed", "method": "rss"},
]


_SOURCE_SELECTORS: dict[str, dict[str, str]] = {
    "qbitai": {
        "container": "article.post, .article-item, .post-item",
        "title": "h2 a, .post-title a, .article-title a",
        "link": "h2 a, .post-title a, .article-title a",
        "summary": ".post-excerpt, .article-excerpt, .entry-summary, p",
        "time": "time, .post-date, .article-date, .date",
    },
    "jiqizhixin": {
        "container": "article, .article-item, .article_content",
        "title": "h2 a, h3 a, .title a",
        "link": "h2 a, h3 a, .title a",
        "summary": ".article-des, .description, p",
        "time": "time, .date, .pub-time",
    },
}


def _get_selectors(source_name: str) -> dict[str, str]:
    """获取源的 CSS 选择器，未知源使用通用选择器."""
    if source_name in _SOURCE_SELECTORS:
        return _SOURCE_SELECTORS[source_name]
    return {
        "container": "article, .article-item, .post-item, .item",
        "title": "h2 a, h3 a, .title a",
        "link": "h2 a, h3 a, .title a",
        "summary": "p, .summary, .description, .excerpt",
        "time": "time, .date, .pub-date",
    }


class ChineseFetcher(BaseFetcher):
    """中文 AI 媒体采集器.

    支持两种模式：
    - RSS: 使用 feedparser 解析 RSS feed
    - Scrape: 使用 httpx + BeautifulSoup 解析网页

    单个源解析失败不影响其他源。
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="chinese", config=config)
        self._chinese_config = self._resolve_config(config)
        self._client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
        )

    def _resolve_config(self, config: Any) -> ChineseConfig:
        """从配置对象提取 ChineseConfig，无配置时使用默认源."""
        if isinstance(config, ChineseConfig):
            if not config.sources:
                return ChineseConfig(
                    sources=[
                        ChineseSourceConfig(**s) for s in DEFAULT_CHINESE_SOURCES
                    ],
                )
            return config
        try:
            from ainews.config.loader import get_config
            app_config = get_config()
            cfg = app_config.sources.chinese
            if not cfg.sources:
                return ChineseConfig(
                    sources=[
                        ChineseSourceConfig(**s) for s in DEFAULT_CHINESE_SOURCES
                    ],
                )
            return cfg
        except Exception:
            return ChineseConfig(
                sources=[
                    ChineseSourceConfig(**s) for s in DEFAULT_CHINESE_SOURCES
                ],
            )

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """从所有已配置的中文源拉取文章."""
        since_ts = self._parse_since(since)
        all_items: list[dict[str, Any]] = []

        for source_cfg in self._chinese_config.sources:
            if not source_cfg.url:
                continue
            try:
                items = self._fetch_source(source_cfg, since_ts)
                all_items.extend(items)
                logger.info(
                    "[chinese] %s (%s) 拉取 %d 条",
                    source_cfg.name, source_cfg.method, len(items),
                )
            except Exception:
                # 容错：单个源失败不影响其他源
                logger.error(
                    "[chinese] %s 解析失败", source_cfg.name, exc_info=True,
                )

            time.sleep(0.5)

        return all_items

    def _parse_since(self, since: Optional[str]) -> float:
        """解析 since 为时间戳."""
        if not since:
            return 0.0
        try:
            dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0

    def _fetch_source(
        self,
        source_cfg: ChineseSourceConfig,
        since_ts: float,
    ) -> list[dict[str, Any]]:
        """拉取单个源的内容."""
        if source_cfg.method == "rss":
            return self._fetch_rss(source_cfg, since_ts)
        return self._fetch_scrape(source_cfg, since_ts)

    # ------------------------------------------------------------------
    # RSS 模式
    # ------------------------------------------------------------------

    def _fetch_rss(
        self,
        source_cfg: ChineseSourceConfig,
        since_ts: float,
    ) -> list[dict[str, Any]]:
        """使用 feedparser 解析 RSS feed."""
        resp = self._client.get(source_cfg.url)
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        items: list[dict[str, Any]] = []

        for entry in feed.entries:
            published_at = self._parse_feed_time(entry)
            if since_ts and published_at:
                if published_at.timestamp() <= since_ts:
                    continue

            url = entry.get("link", "")
            if not url:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")

            items.append({
                "url": url,
                "title": title,
                "content_raw": summary,
                "source": "chinese",
                "source_name": source_cfg.name,
                "author": entry.get("author", ""),
                "published_at": published_at,
                "time": published_at.isoformat() if published_at else "",
            })

        return items

    # ------------------------------------------------------------------
    # 网页解析模式
    # ------------------------------------------------------------------

    def _fetch_scrape(
        self,
        source_cfg: ChineseSourceConfig,
        since_ts: float,
    ) -> list[dict[str, Any]]:
        """使用 BeautifulSoup 解析网页."""
        resp = self._client.get(source_cfg.url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        selectors = _get_selectors(source_cfg.name)
        containers = soup.select(selectors["container"])

        items: list[dict[str, Any]] = []

        for container in containers:
            try:
                item = self._parse_container(container, selectors, source_cfg, since_ts)
                if item is not None:
                    items.append(item)
            except Exception:
                logger.debug(
                    "[chinese] %s 容器解析跳过", source_cfg.name, exc_info=True,
                )

        return items

    def _parse_container(
        self,
        container: Any,
        selectors: dict[str, str],
        source_cfg: ChineseSourceConfig,
        since_ts: float,
    ) -> Optional[dict[str, Any]]:
        """解析单个容器元素."""
        # 提取标题和链接
        title_el = container.select_one(selectors["title"])
        if title_el is None:
            return None
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        if not url or not title:
            return None

        # 补全相对 URL
        if url.startswith("/"):
            base = source_cfg.url.rstrip("/")
            url = f"{base}{url}"

        # 提取摘要
        summary_el = container.select_one(selectors["summary"])
        summary = summary_el.get_text(strip=True) if summary_el else ""

        # 提取时间
        published_at = None
        time_el = container.select_one(selectors["time"])
        if time_el:
            published_at = self._parse_html_time(time_el)

        # 增量过滤
        if since_ts and published_at:
            if published_at.timestamp() <= since_ts:
                return None

        return {
            "url": url,
            "title": title,
            "content_raw": summary,
            "source": "chinese",
            "source_name": source_cfg.name,
            "author": "",
            "published_at": published_at,
            "time": published_at.isoformat() if published_at else "",
        }

    # ------------------------------------------------------------------
    # 时间解析辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_feed_time(entry: Any) -> Optional[datetime]:
        """从 feedparser entry 解析发布时间."""
        for attr in ("published_parsed", "updated_parsed"):
            time_tuple = getattr(entry, attr, None)
            if time_tuple:
                try:
                    import time as _time
                    ts = _time.mktime(time_tuple)
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                except (ValueError, TypeError, OverflowError):
                    continue
        return None

    @staticmethod
    def _parse_html_time(element: Any) -> Optional[datetime]:
        """从 HTML time 元素解析时间."""
        # 优先取 datetime 属性
        dt_str = element.get("datetime", "")
        if dt_str:
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # 尝试解析文本内容
        text = element.get_text(strip=True)
        if text:
            for fmt in (
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y年%m月%d日",
                "%Y/%m/%d",
            ):
                try:
                    return datetime.strptime(text, fmt).replace(
                        tzinfo=timezone.utc,
                    )
                except ValueError:
                    continue

        return None

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最大的 published_at 作为水印."""
        if not items:
            return None
        times = [item.get("time", "") for item in items if item.get("time")]
        return max(times) if times else None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试中文源连通性."""
        sources = self._chinese_config.sources
        if not sources:
            return {"ok": False, "error": "未配置任何中文源"}

        results: list[str] = []
        ok_count = 0

        for source_cfg in sources:
            try:
                start = time.monotonic()
                resp = self._client.get(source_cfg.url, timeout=10)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    results.append(f"{source_cfg.name}: OK ({latency}ms)")
                    ok_count += 1
                else:
                    results.append(f"{source_cfg.name}: HTTP {resp.status_code}")
            except Exception as e:
                results.append(f"{source_cfg.name}: {e}")

        if ok_count == len(sources):
            return {
                "ok": True,
                "latency_ms": 0,
                "detail": "; ".join(results),
            }
        if ok_count > 0:
            return {
                "ok": True,
                "latency_ms": 0,
                "detail": f"部分可用: {'; '.join(results)}",
            }
        return {"ok": False, "error": "; ".join(results)}
