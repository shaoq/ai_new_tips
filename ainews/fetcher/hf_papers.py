"""HuggingFace Daily Papers 采集器 — REST API，无认证."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from ainews.config.settings import HFPapersConfig
from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

HF_PAPERS_API = "https://huggingface.co/api/daily_papers"


class HFPapersFetcher(BaseFetcher):
    """HuggingFace Daily Papers 采集器.

    通过 HuggingFace REST API 拉取每日精选论文，
    upvotes 作为热度信号。
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="hf_papers", config=config)
        self._hf_config = self._resolve_config(config)
        self._client = httpx.Client(timeout=30.0)
        self._last_request_time: float = 0.0

    def _resolve_config(self, config: Any) -> HFPapersConfig:
        """从配置对象提取 HFPapersConfig."""
        if isinstance(config, HFPapersConfig):
            return config
        try:
            from ainews.config.loader import get_config
            app_config = get_config()
            return app_config.sources.hf_papers
        except Exception:
            return HFPapersConfig()

    def _rate_limit(self) -> None:
        """自限 1 req/2s."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)
        self._last_request_time = time.monotonic()

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """拉取 HuggingFace Daily Papers."""
        days = backfill_days or 1
        # 如果有 cursor (last_date)，计算从 cursor 到今天的天数
        if since:
            try:
                last_date = datetime.fromisoformat(since).date()
                today = datetime.now(tz=timezone.utc).date()
                days = max(1, (today - last_date).days)
            except (ValueError, TypeError):
                days = 1

        all_items: list[dict[str, Any]] = []
        today = datetime.now(tz=timezone.utc).date()

        for i in range(days):
            target_date = today - timedelta(days=i)
            date_str = target_date.isoformat()

            try:
                items = self._fetch_by_date(date_str)
                all_items.extend(items)
                logger.info("[hf_papers] %s 拉取 %d 篇论文", date_str, len(items))
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("[hf_papers] 速率限制，退避 30s")
                    time.sleep(30)
                    items = self._fetch_by_date(date_str)
                    all_items.extend(items)
                elif e.response.status_code == 400:
                    logger.info("[hf_papers] %s 暂无数据（当日论文尚未发布）", date_str)
                else:
                    logger.error("[hf_papers] %s 请求失败: %s", date_str, e)
            except Exception:
                logger.error("[hf_papers] %s 异常", date_str, exc_info=True)

            self._rate_limit()

        # 按 min_upvotes 过滤
        min_upvotes = self._hf_config.min_upvotes
        if min_upvotes > 0:
            before_count = len(all_items)
            all_items = [
                item for item in all_items
                if item.get("metrics", {}).get("upvote_count", 0) >= min_upvotes
            ]
            logger.info(
                "[hf_papers] upvotes>=%d 过滤: %d → %d",
                min_upvotes, before_count, len(all_items),
            )

        return all_items

    def _fetch_by_date(self, date_str: str) -> list[dict[str, Any]]:
        """拉取指定日期的论文."""
        self._rate_limit()
        resp = self._client.get(HF_PAPERS_API, params={"date": date_str})
        resp.raise_for_status()
        papers: list[dict[str, Any]] = resp.json()

        return [self._normalize(p) for p in papers if self._normalize(p) is not None]

    # ------------------------------------------------------------------
    # normalize
    # ------------------------------------------------------------------

    def _normalize(self, paper: dict[str, Any]) -> Optional[dict[str, Any]]:
        """将 HF Paper 映射为统一 Article 字典."""
        paper_info = paper.get("paper", {})
        if not paper_info:
            return None

        pid = paper_info.get("id", "")
        if not pid:
            return None

        title = paper_info.get("title", "")
        abstract = paper_info.get("abstract", "")
        authors = [
            a.get("name", "") if isinstance(a, dict) else str(a)
            for a in paper_info.get("authors", [])
        ]

        published_at: Optional[datetime] = None
        published_str = paper.get("publishedAt", "")
        if published_str:
            try:
                published_at = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00"),
                )
            except (ValueError, TypeError):
                published_at = None

        return {
            "url": f"https://huggingface.co/papers/{pid}",
            "title": title,
            "content_raw": abstract,
            "source": "hf_papers",
            "source_name": "HuggingFace Papers",
            "author": ", ".join(authors),
            "published_at": published_at,
            "time": published_at.isoformat() if published_at else "",
            "metrics": {
                "upvote_count": paper.get("paper", {}).get("upvotes", 0),
                "platform_score": float(paper.get("paper", {}).get("upvotes", 0)),
            },
        }

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最大的 published_at 日期作为水印."""
        if not items:
            return None
        dates = []
        for item in items:
            pa = item.get("published_at")
            if pa:
                if isinstance(pa, datetime):
                    dates.append(pa.date().isoformat())
                else:
                    dates.append(str(pa)[:10])
        return max(dates) if dates else None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试 HuggingFace API 连通性."""
        try:
            start = time.monotonic()
            today = datetime.now(tz=timezone.utc).date().isoformat()
            resp = self._client.get(
                HF_PAPERS_API, params={"date": today}, timeout=10,
            )
            latency = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "detail": f"今日论文 {len(data)} 篇",
                }
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
