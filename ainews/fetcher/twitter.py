"""Twitter/X 数据源 — 基于 SocialData.tools API.

支持两种采集模式：
- 账户监控：拉取指定 AI KOL 的最新推文
- 热门搜索：按关键词搜索高互动量 AI 推文
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from ainews.fetcher.base import BaseFetcher

logger = logging.getLogger(__name__)

SOCIALDATA_BASE = "https://api.socialdata.tools"

DEFAULT_SEARCH_QUERY = (
    '(AI OR LLM OR GPT OR "machine learning" OR "deep learning") '
    "min_faves:100 -is:retweet lang:en"
)


class TwitterFetcher(BaseFetcher):
    """X/Twitter 采集器（SocialData.tools API）."""

    def __init__(self, config: Any = None) -> None:
        super().__init__(source_name="twitter", config=config)
        self._twitter_config = self._resolve_config()
        self._client: httpx.Client | None = None
        self._user_id_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 配置解析
    # ------------------------------------------------------------------

    def _resolve_config(self) -> Any:
        """从传入 config 或 AppConfig 提取 TwitterConfig."""
        if self.config is not None:
            return self.config
        try:
            from ainews.config.loader import get_config
            return get_config().sources.twitter
        except Exception:
            return None

    def _get_api_key(self) -> str:
        if self._twitter_config is None:
            return ""
        return getattr(self._twitter_config, "api_key", "")

    # ------------------------------------------------------------------
    # HTTP 客户端
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=SOCIALDATA_BASE,
                headers={
                    "Authorization": f"Bearer {self._get_api_key()}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    # ------------------------------------------------------------------
    # 用户 ID 解析
    # ------------------------------------------------------------------

    def _resolve_user_id(self, screen_name: str) -> Optional[str]:
        """将 screen_name 解析为 user_id，结果缓存."""
        if screen_name in self._user_id_cache:
            return self._user_id_cache[screen_name]

        client = self._get_client()
        try:
            resp = client.get(f"/twitter/user/{screen_name}")
            if resp.status_code == 404:
                logger.warning("[twitter] 用户不存在: @%s", screen_name)
                return None
            resp.raise_for_status()
            data = resp.json()
            user_id = str(data.get("id_str", ""))
            if user_id:
                self._user_id_cache[screen_name] = user_id
                logger.debug("[twitter] 解析 @%s → user_id=%s", screen_name, user_id)
                return user_id
        except httpx.HTTPError as exc:
            logger.warning("[twitter] 解析用户 ID 失败 @%s: %s", screen_name, exc)
        return None

    # ------------------------------------------------------------------
    # 账户模式
    # ------------------------------------------------------------------

    def _fetch_account_tweets(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """拉取所有监控账户的推文."""
        if self._twitter_config is None:
            return []

        accounts = getattr(self._twitter_config, "accounts", [])
        if not accounts:
            return []

        all_items: list[dict[str, Any]] = []
        client = self._get_client()

        for screen_name in accounts:
            user_id = self._resolve_user_id(screen_name)
            if user_id is None:
                continue

            try:
                params: dict[str, Any] = {}
                if since:
                    params["cursor"] = since

                resp = client.get(f"/twitter/user/{user_id}/tweets", params=params)
                if resp.status_code == 402:
                    logger.warning("[twitter] API 余额不足（HTTP 402），停止采集")
                    break
                resp.raise_for_status()
                data = resp.json()
                tweets = data.get("tweets", [])

                for tweet in tweets:
                    if self._filter_tweet(tweet):
                        all_items.append(self._normalize_tweet(tweet))

                logger.info(
                    "[twitter] @%s: 拉取 %d 条，过滤后 %d 条",
                    screen_name, len(tweets), sum(1 for t in tweets if self._filter_tweet(t)),
                )

                # 速率控制：避免超过 120 req/min
                time.sleep(0.6)

            except httpx.HTTPError as exc:
                logger.warning("[twitter] 拉取 @%s 推文失败: %s", screen_name, exc)

        return all_items

    # ------------------------------------------------------------------
    # 搜索模式
    # ------------------------------------------------------------------

    def _fetch_search_tweets(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """按关键词搜索热门推文."""
        if self._twitter_config is None:
            return []

        search_queries = getattr(self._twitter_config, "search_queries", [])
        if not search_queries:
            search_queries = [DEFAULT_SEARCH_QUERY]

        all_items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        client = self._get_client()

        for query in search_queries:
            full_query = query
            if since:
                full_query = f"{query} since_id:{since}"

            try:
                params = {"query": full_query, "type": "Top"}
                resp = client.get("/twitter/search", params=params)
                if resp.status_code == 402:
                    logger.warning("[twitter] API 余额不足（HTTP 402），停止搜索")
                    break
                resp.raise_for_status()
                data = resp.json()
                tweets = data.get("tweets", [])

                for tweet in tweets:
                    tweet_id = tweet.get("id_str", "")
                    if tweet_id and tweet_id not in seen_ids:
                        seen_ids.add(tweet_id)
                        all_items.append(self._normalize_tweet(tweet))

                logger.info("[twitter] 搜索 '%s...': 返回 %d 条", query[:50], len(tweets))

                time.sleep(0.6)

            except httpx.HTTPError as exc:
                logger.warning("[twitter] 搜索失败 '%s...': %s", query[:50], exc)

        return all_items

    # ------------------------------------------------------------------
    # 数据标准化
    # ------------------------------------------------------------------

    def _normalize_tweet(self, tweet: dict[str, Any]) -> dict[str, Any]:
        """将 SocialData API 推文 JSON 标准化为统一条目格式."""
        user = tweet.get("user", {})
        screen_name = user.get("screen_name", "unknown")
        tweet_id = tweet.get("id_str", "")
        full_text = tweet.get("full_text") or tweet.get("text", "")

        # 处理推文中的外部链接
        entities = tweet.get("entities", {})
        urls = entities.get("urls", [])
        external_links = []
        for url_obj in urls:
            expanded = url_obj.get("expanded_url", "")
            if expanded and not expanded.startswith("https://x.com/"):
                external_links.append(expanded)

        content_raw = full_text
        if external_links:
            content_raw = f"{full_text}\n\nLinks: {' '.join(external_links)}"

        title = full_text[:200] + ("..." if len(full_text) > 200 else "")

        # 解析发布时间
        published_at = None
        created_at_str = tweet.get("tweet_created_at", "")
        if created_at_str:
            try:
                published_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        favorite_count = tweet.get("favorite_count", 0)
        reply_count = tweet.get("reply_count", 0)

        return {
            "url": f"https://x.com/{screen_name}/status/{tweet_id}",
            "title": title,
            "content_raw": content_raw,
            "source": "twitter",
            "source_name": f"@{screen_name}",
            "author": user.get("name", screen_name),
            "published_at": published_at,
            "time": tweet.get("tweet_created_at", ""),
            "metrics": {
                "platform_score": float(favorite_count),
                "upvote_count": favorite_count,
                "comment_count": reply_count,
            },
        }

    # ------------------------------------------------------------------
    # 过滤
    # ------------------------------------------------------------------

    def _filter_tweet(self, tweet: dict[str, Any]) -> bool:
        """过滤低质量推文：回复、转推、短文本、低互动量."""
        # 过滤转推
        if tweet.get("retweeted_status") is not None:
            return False

        # 过滤纯回复
        if tweet.get("in_reply_to_status_id_str"):
            return False

        # 过滤短文本
        full_text = tweet.get("full_text") or tweet.get("text", "")
        if len(full_text) < 20:
            return False

        # 过滤低互动量
        min_engagement = 0
        if self._twitter_config is not None:
            min_engagement = getattr(self._twitter_config, "min_engagement", 0)
        favorite_count = tweet.get("favorite_count", 0)
        if favorite_count < min_engagement:
            return False

        return True

    # ------------------------------------------------------------------
    # BaseFetcher 抽象方法实现
    # ------------------------------------------------------------------

    def fetch_items(
        self,
        since: Optional[str] = None,
        backfill_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """合并账户模式和搜索模式结果."""
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("[twitter] 未配置 api_key，跳过采集")
            return []

        items: list[dict[str, Any]] = []

        # 账户模式
        account_items = self._fetch_account_tweets(since=since)
        items.extend(account_items)

        # 搜索模式
        search_items = self._fetch_search_tweets(since=since)
        items.extend(search_items)

        # 按 tweet ID 去重（URL 去重由基类处理，这里做内存级快速去重）
        seen_urls: set[str] = set()
        unique_items: list[dict[str, Any]] = []
        for item in items:
            url = item.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        logger.info("[twitter] 合并后 %d 条（去重后 %d 条）", len(items), len(unique_items))
        return unique_items

    def _build_cursor(self, items: list[dict[str, Any]]) -> Optional[str]:
        """使用最新 tweet ID 作为水印."""
        if not items:
            return None
        # 从 URL 中提取 tweet ID: https://x.com/{user}/status/{id}
        tweet_ids = []
        for item in items:
            url = item.get("url", "")
            parts = url.rsplit("/", 1)
            if len(parts) == 2 and parts[1].isdigit():
                tweet_ids.append(parts[1])
        if tweet_ids:
            return max(tweet_ids)
        return None

    def test_connection(self) -> dict[str, Any]:
        """测试 SocialData API 连通性."""
        api_key = self._get_api_key()
        if not api_key:
            return {"ok": False, "error": "未配置 api_key"}

        start = time.monotonic()
        try:
            client = self._get_client()
            resp = client.get("/twitter/user/elonmusk")
            elapsed = int((time.monotonic() - start) * 1000)

            if resp.status_code in (200, 404):
                return {"ok": True, "latency_ms": elapsed, "detail": "SocialData API 连通正常"}
            if resp.status_code == 402:
                return {"ok": False, "error": "API 余额不足（HTTP 402）"}
            return {
                "ok": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        except httpx.HTTPError as exc:
            return {"ok": False, "error": str(exc)}
