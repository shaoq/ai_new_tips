"""推送策略引擎：去重、每日上限、文章查询."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlmodel import Session, select, func, col

from ainews.storage.models import Article, PushLog

logger = logging.getLogger(__name__)

# 每日 actionCard 推送上限
DAILY_ACTIONCARD_LIMIT = 3

# 热点阈值
TREND_SCORE_HIGH = 8.0
TREND_SCORE_INSTANT = 8.5


class PushStrategy:
    """推送策略引擎."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # 3.1 判断是否推送
    # ------------------------------------------------------------------

    def should_push(
        self,
        article: Article,
        push_type: str,
    ) -> bool:
        """判断文章是否应该推送.

        逻辑:
        - dingtalk_sent 为 True 时，feedCard 不再推送；actionCard 允许单独推送
        - actionCard 需检查每日上限
        """
        # feedCard: 已推送则跳过
        if push_type == "feedcard" and article.dingtalk_sent:
            return False

        # actionCard: 检查是否已通过 actionCard 推送过
        if push_type == "actioncard":
            if self._is_actioncard_sent(article.id):
                return False
            # 检查每日上限
            if self._daily_actioncard_count() >= DAILY_ACTIONCARD_LIMIT:
                logger.info(
                    "今日 actionCard 已达上限 %d 篇，跳过: %s",
                    DAILY_ACTIONCARD_LIMIT,
                    article.title,
                )
                return False

        return True

    # ------------------------------------------------------------------
    # 3.2 去重查询
    # ------------------------------------------------------------------

    def _is_actioncard_sent(self, article_id: int) -> bool:
        """检查文章是否已通过 actionCard 推送."""
        stmt = (
            select(func.count())
            .select_from(PushLog)
            .where(PushLog.article_id == article_id)
            .where(PushLog.push_type == "actioncard")
        )
        count = self._session.exec(stmt).one()
        return count > 0

    def is_feedcard_sent(self, article_id: int) -> bool:
        """检查文章是否已通过 feedCard 推送."""
        stmt = (
            select(func.count())
            .select_from(PushLog)
            .where(PushLog.article_id == article_id)
            .where(PushLog.push_type == "feedcard")
        )
        count = self._session.exec(stmt).one()
        return count > 0

    # ------------------------------------------------------------------
    # 3.3 每日计数器
    # ------------------------------------------------------------------

    def _daily_actioncard_count(self) -> int:
        """查询今日 actionCard 推送数量."""
        today = date.today()
        stmt = (
            select(func.count())
            .select_from(PushLog)
            .where(PushLog.push_type == "actioncard")
            .where(col(PushLog.pushed_at) >= datetime.combine(today, datetime.min.time()))
        )
        return self._session.exec(stmt).one()

    def daily_actioncard_count(self) -> int:
        """公开接口：查询今日 actionCard 推送数量."""
        return self._daily_actioncard_count()

    # ------------------------------------------------------------------
    # 3.4 午间跳过逻辑
    # ------------------------------------------------------------------

    def should_skip_noon(self) -> bool:
        """判断午间推送是否应跳过（无 trend_score >= 8 的新热点时跳过）."""
        articles = self._query_noon_articles()
        return len(articles) == 0

    # ------------------------------------------------------------------
    # 3.5 文章查询
    # ------------------------------------------------------------------

    def query_morning_articles(self, limit: int = 10) -> list[Article]:
        """查询晨报文章: Top N by trend_score, 未推送."""
        stmt = (
            select(Article)
            .where(Article.dingtalk_sent == False)  # noqa: E712
            .where(Article.processed == True)  # noqa: E712
            .order_by(col(Article.trend_score).desc())
            .limit(limit)
        )
        return list(self._session.exec(stmt).all())

    def query_evening_articles(self) -> list[Article]:
        """查询晚报文章: 全部增量（今日 fetched_at）, 未推送."""
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        stmt = (
            select(Article)
            .where(Article.dingtalk_sent == False)  # noqa: E712
            .where(Article.processed == True)  # noqa: E712
            .where(col(Article.fetched_at) >= today_start)
            .order_by(col(Article.trend_score).desc())
        )
        return list(self._session.exec(stmt).all())

    def _query_noon_articles(self) -> list[Article]:
        """查询午间热点: trend_score >= 8, 今日新文章."""
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        stmt = (
            select(Article)
            .where(Article.processed == True)  # noqa: E712
            .where(col(Article.trend_score) >= TREND_SCORE_HIGH)
            .where(col(Article.fetched_at) >= today_start)
            .order_by(col(Article.trend_score).desc())
        )
        return list(self._session.exec(stmt).all())

    def query_noon_articles(self) -> list[Article]:
        """公开接口：查询午间热点文章."""
        return self._query_noon_articles()

    def query_trending_articles(self) -> list[Article]:
        """查询热点文章: trend_score >= 8, 未推送."""
        stmt = (
            select(Article)
            .where(Article.dingtalk_sent == False)  # noqa: E712
            .where(Article.processed == True)  # noqa: E712
            .where(col(Article.trend_score) >= TREND_SCORE_HIGH)
            .order_by(col(Article.trend_score).desc())
        )
        return list(self._session.exec(stmt).all())

    def query_article_by_slug(self, slug: str) -> Article | None:
        """根据 slug 查询单篇文章（按 URL 模糊匹配或标题）."""
        # 先按 URL 匹配
        stmt = select(Article).where(Article.url.contains(slug))
        result = self._session.exec(stmt).first()
        if result is not None:
            return result

        # 再按标题匹配
        stmt = select(Article).where(Article.title.contains(slug))
        return self._session.exec(stmt).first()

    def query_weekly_stats(self) -> dict[str, Any]:
        """查询本周统计数据."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_dt = datetime.combine(week_start, datetime.min.time())

        # 本周总数
        total_stmt = (
            select(func.count())
            .select_from(Article)
            .where(col(Article.fetched_at) >= week_start_dt)
        )
        total = self._session.exec(total_stmt).one()

        # 分类分布
        cat_stmt = (
            select(Article.category, func.count())
            .where(col(Article.fetched_at) >= week_start_dt)
            .group_by(Article.category)
        )
        categories = dict(self._session.exec(cat_stmt).all())

        return {
            "total": total,
            "categories": categories,
        }

    def query_weekly_top_articles(self, limit: int = 5) -> list[Article]:
        """查询本周 Top N 热点文章."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_dt = datetime.combine(week_start, datetime.min.time())

        stmt = (
            select(Article)
            .where(col(Article.fetched_at) >= week_start_dt)
            .where(Article.processed == True)  # noqa: E712
            .order_by(col(Article.trend_score).desc())
            .limit(limit)
        )
        return list(self._session.exec(stmt).all())
