"""HackerNews 采集器 — Firebase API (实时) + Algolia API (回填)."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_BASE = "http://hn.algolia.com/api/v1"

AI_KEYWORDS: list[str] = [
    "ai", "llm", "gpt", "claude", "gemini", "machine learning", "deep learning",
    "neural network", "transformer", "diffusion", "agi", "chatgpt", "openai",
    "anthropic", "deepmind", "computer vision", "nlp", "generative", "embedding",
    "fine-tuning", "rag", "agent", "mcp", "reasoning", "multimodal", "llama",
    "mistral", "grok", "copilot", "prompt", "sora", "midjourney", "stable diffusion",
    "dalle", "image generation", "language model", "foundation model",
    "artificial intelligence",
    # Agentic coding tools
    "agentic", "cursor", "windsurf", "codex", "aider", "coding assistant",
    "computer use",
]

_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in AI_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _is_ai_related(title: str) -> bool:
    """判断标题是否与 AI 相关."""
    return bool(_KEYWORD_PATTERN.search(title))


class HackerNewsFetcher(BaseFetcher):
    """HackerNews 采集器.

    - 正常模式: Firebase API topstories + item 详情
    - 回填模式: Algolia Search API 时间范围搜索
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="hackernews", config=config)
        self._client = httpx.Client(timeout=30.0)

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """拉取 HackerNews 条目."""
        if backfill_days is not None and backfill_days > 0:
            return self._fetch_via_algolia(backfill_days=backfill_days)
        return self._fetch_via_firebase(since=since)

    # ------------------------------------------------------------------
    # Firebase API
    # ------------------------------------------------------------------

    def _fetch_via_firebase(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """通过 Firebase API 获取实时热门故事."""
        since_ts = float(since) if since else 0.0

        # 获取 topstories ID 列表
        resp = self._client.get(f"{FIREBASE_BASE}/topstories.json")
        resp.raise_for_status()
        story_ids: list[int] = resp.json()

        items: list[dict[str, Any]] = []
        max_items = 500  # HN topstories 最多约 500 条

        for idx, story_id in enumerate(story_ids[:max_items]):
            try:
                detail = self._fetch_item(story_id)
                if detail is None:
                    continue

                item_time = detail.get("time", 0)
                # 增量过滤
                if since_ts and item_time <= since_ts:
                    continue

                title = detail.get("title", "")
                if not _is_ai_related(title):
                    continue

                url = detail.get("url", "")
                if not url:
                    continue  # 跳过 Ask HN 等无 URL 的帖子

                items.append({
                    "url": url,
                    "title": title,
                    "content_raw": detail.get("text", ""),
                    "source": "hackernews",
                    "source_name": "HackerNews",
                    "author": detail.get("by", ""),
                    "published_at": datetime.fromtimestamp(item_time, tz=timezone.utc),
                    "time": item_time,
                    "metrics": {
                        "platform_score": float(detail.get("score", 0)),
                        "comment_count": detail.get("descendants", 0),
                    },
                })
            except Exception:
                logger.warning("获取 HN item %d 失败", story_id, exc_info=True)

            # 社区约定 ~1 req/sec
            if idx > 0 and idx % 10 == 0:
                time.sleep(0.5)

        return items

    def _fetch_item(self, item_id: int) -> Optional[dict[str, Any]]:
        """获取单条 HN item 详情."""
        resp = self._client.get(f"{FIREBASE_BASE}/item/{item_id}.json")
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data is None or data.get("type") != "story":
            return None
        return data

    # ------------------------------------------------------------------
    # Algolia API
    # ------------------------------------------------------------------

    def _fetch_via_algolia(self, backfill_days: int) -> list[dict[str, Any]]:
        """通过 Algolia API 搜索历史数据（回填模式）."""
        since_date = datetime.now(tz=timezone.utc) - timedelta(days=backfill_days)
        since_ts = int(since_date.timestamp())

        # 构建 AI 关键词搜索查询
        query_parts = " OR ".join(AI_KEYWORDS[:10])  # Algolia 查询不宜太长
        params = {
            "query": query_parts,
            "numericFilters": f"points>10,created_at_i>{since_ts}",
            "tags": "story",
            "hitsPerPage": 100,
        }

        resp = self._client.get(f"{ALGOLIA_BASE}/search", params=params)
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits", [])
        items: list[dict[str, Any]] = []

        for hit in hits:
            title = hit.get("title", "")
            if not _is_ai_related(title):
                continue

            url = hit.get("url", "")
            if not url:
                continue

            created_at_str = hit.get("created_at", "")
            published_at: Optional[datetime] = None
            if created_at_str:
                try:
                    published_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    published_at = None

            created_at_i = hit.get("created_at_i", 0)

            items.append({
                "url": url,
                "title": title,
                "content_raw": "",
                "source": "hackernews",
                "source_name": "HackerNews",
                "author": hit.get("author", ""),
                "published_at": published_at,
                "time": float(created_at_i),
                "metrics": {
                    "platform_score": float(hit.get("points", 0)),
                    "comment_count": hit.get("num_comments", 0),
                },
            })

        return items

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最大的 time 作为水印."""
        if not items:
            return None
        timestamps = [item.get("time", 0) for item in items]
        return str(max(timestamps)) if timestamps else None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试 Firebase API 连通性."""
        try:
            start = time.monotonic()
            resp = self._client.get(f"{FIREBASE_BASE}/topstories.json", timeout=10)
            latency = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "detail": f"topstories 返回 {len(data)} 条 ID",
                }
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
