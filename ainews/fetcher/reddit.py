"""Reddit 采集器 — PRAW OAuth2，多 subreddit 监控."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import praw
import prawcore

from ainews.config.settings import RedditConfig
from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

AI_KEYWORDS: list[str] = [
    "ai", "llm", "gpt", "claude", "gemini", "machine learning", "deep learning",
    "neural network", "transformer", "diffusion", "agi", "chatgpt", "openai",
    "anthropic", "deepmind", "computer vision", "nlp", "generative", "embedding",
    "fine-tuning", "rag", "agent", "mcp", "reasoning", "multimodal", "llama",
    "mistral", "grok", "copilot", "prompt", "sora", "midjourney",
    "language model", "foundation model", "artificial intelligence",
]

_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in AI_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _is_ai_related(title: str) -> bool:
    """判断标题是否与 AI 相关."""
    return bool(_KEYWORD_PATTERN.search(title))


class RedditFetcher(BaseFetcher):
    """Reddit 采集器.

    通过 PRAW 访问 Reddit API，拉取指定 subreddit 的 hot + new 帖子，
    过滤 AI 关键词，记录 score/comments 作为热度信号。
    """

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="reddit", config=config)
        self._reddit_config = self._resolve_config(config)
        self._reddit: praw.Reddit | None = None

    def _resolve_config(self, config: Any) -> RedditConfig:
        """从配置对象提取 RedditConfig."""
        if isinstance(config, RedditConfig):
            return config
        # 从 AppConfig.sources.reddit 提取
        try:
            from ainews.config.loader import get_config
            app_config = get_config()
            return app_config.sources.reddit
        except Exception:
            return RedditConfig()

    def _get_reddit(self) -> praw.Reddit:
        """懒加载 PRAW Reddit 实例."""
        if self._reddit is None:
            cfg = self._reddit_config
            if not cfg.client_id or not cfg.client_secret:
                msg = "Reddit OAuth2 凭证未配置，请设置 client_id 和 client_secret"
                raise ValueError(msg)
            self._reddit = praw.Reddit(
                client_id=cfg.client_id,
                client_secret=cfg.client_secret,
                user_agent=cfg.user_agent,
            )
        return self._reddit

    # ------------------------------------------------------------------
    # fetch_items
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """从多个 subreddit 拉取帖子."""
        reddit = self._get_reddit()
        since_ts = float(since) if since else 0.0
        all_items: list[dict[str, Any]] = []

        for subreddit_name in self._reddit_config.subreddits:
            try:
                items = self._fetch_subreddit(reddit, subreddit_name, since_ts)
                all_items.extend(items)
                logger.info(
                    "[reddit] r/%s 拉取 %d 条帖子", subreddit_name, len(items),
                )
            except prawcore.exceptions.ResponseException as e:
                if e.response.status_code == 401:
                    msg = "Reddit OAuth2 凭证无效，请检查 client_id 和 client_secret"
                    raise ValueError(msg) from e
                logger.error("[reddit] r/%s 请求失败: %s", subreddit_name, e)
            except prawcore.exceptions.RequestException as e:
                logger.error("[reddit] r/%s 网络错误: %s", subreddit_name, e)
            except Exception:
                logger.error("[reddit] r/%s 异常", subreddit_name, exc_info=True)

            # 速率限制退避
            time.sleep(1.0)

        return all_items

    def _fetch_subreddit(
        self,
        reddit: praw.Reddit,
        subreddit_name: str,
        since_ts: float,
    ) -> list[dict[str, Any]]:
        """拉取单个 subreddit 的 hot + new 帖子."""
        subreddit = reddit.subreddit(subreddit_name)
        seen_ids: set[str] = set()
        items: list[dict[str, Any]] = []

        for submission in subreddit.hot(limit=50):
            item = self._process_submission(submission, subreddit_name, since_ts, seen_ids)
            if item is not None:
                items.append(item)

        for submission in subreddit.new(limit=50):
            item = self._process_submission(submission, subreddit_name, since_ts, seen_ids)
            if item is not None:
                items.append(item)

        return items

    def _process_submission(
        self,
        submission: praw.models.Submission,
        subreddit_name: str,
        since_ts: float,
        seen_ids: set[str],
    ) -> Optional[dict[str, Any]]:
        """处理单条 submission，返回标准化 item 或 None."""
        if submission.id in seen_ids:
            return None
        seen_ids.add(submission.id)

        # 增量过滤
        created_utc = float(submission.created_utc)
        if since_ts and created_utc <= since_ts:
            return None

        title = submission.title
        if not _is_ai_related(title):
            return None

        # 跳过置顶/公告帖
        if submission.stickied:
            return None

        url = submission.url
        # Reddit 自身链接（文字帖）使用 permalink
        if url.startswith("https://www.reddit.com/"):
            url = f"https://www.reddit.com{submission.permalink}"

        return self._normalize(submission, subreddit_name)

    # ------------------------------------------------------------------
    # normalize
    # ------------------------------------------------------------------

    def _normalize(
        self, submission: praw.models.Submission, subreddit_name: str,
    ) -> dict[str, Any]:
        """将 PRAW Submission 映射为统一 Article 字典."""
        url = submission.url
        if url.startswith("https://www.reddit.com/"):
            url = f"https://www.reddit.com{submission.permalink}"

        return {
            "url": url,
            "title": submission.title,
            "content_raw": submission.selftext or "",
            "source": "reddit",
            "source_name": f"r/{subreddit_name}",
            "author": str(submission.author) if submission.author else "[deleted]",
            "published_at": datetime.fromtimestamp(
                submission.created_utc, tz=timezone.utc,
            ),
            "time": float(submission.created_utc),
            "metrics": {
                "platform_score": float(submission.score),
                "comment_count": submission.num_comments,
            },
        }

    # ------------------------------------------------------------------
    # 水印
    # ------------------------------------------------------------------

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最大的 created_utc 作为水印."""
        if not items:
            return None
        timestamps = [item.get("time", 0) for item in items]
        return str(max(timestamps)) if timestamps else None

    # ------------------------------------------------------------------
    # 连通性测试
    # ------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """测试 Reddit API 连通性."""
        try:
            start = time.monotonic()
            reddit = self._get_reddit()
            # 尝试获取已认证用户信息验证凭证
            reddit.user.me()
            latency = int((time.monotonic() - start) * 1000)
            return {
                "ok": True,
                "latency_ms": latency,
                "detail": "Reddit API 认证成功",
            }
        except prawcore.exceptions.ResponseException as e:
            if e.response.status_code == 401:
                return {"ok": False, "error": "OAuth2 凭证无效"}
            return {"ok": False, "error": f"HTTP {e.response.status_code}"}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
