"""测试推送策略引擎：去重、每日上限、午间跳过、文章查询."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ainews.storage.models import Article, PushLog
from ainews.publisher.strategy import (
    DAILY_ACTIONCARD_LIMIT,
    TREND_SCORE_HIGH,
    PushStrategy,
)


@pytest.fixture
def engine():
    """创建内存 SQLite 引擎."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """创建测试 Session."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def strategy(session: Session) -> PushStrategy:
    """创建 PushStrategy 实例."""
    return PushStrategy(session)


def _make_article(
    session: Session,
    *,
    url: str = "https://example.com/1",
    title: str = "Test Article",
    trend_score: float = 5.0,
    dingtalk_sent: bool = False,
    processed: bool = True,
    fetched_at: datetime | None = None,
    source: str = "hackernews",
    source_name: str = "HackerNews",
    category: str = "LLM",
) -> Article:
    """创建测试文章."""
    article = Article(
        url=url,
        title=title,
        trend_score=trend_score,
        dingtalk_sent=dingtalk_sent,
        processed=processed,
        fetched_at=fetched_at or datetime.now(),
        source=source,
        source_name=source_name,
        category=category,
    )
    session.add(article)
    session.flush()
    return article


class TestShouldPush:
    """测试推送判断逻辑."""

    def test_feedcard_unsent(self, strategy: PushStrategy, session: Session) -> None:
        """未推送文章应允许 feedCard 推送."""
        article = _make_article(session)
        assert strategy.should_push(article, "feedcard") is True

    def test_feedcard_already_sent(self, strategy: PushStrategy, session: Session) -> None:
        """已推送文章不应再 feedCard 推送."""
        article = _make_article(session, dingtalk_sent=True)
        assert strategy.should_push(article, "feedcard") is False

    def test_actioncard_not_sent(self, strategy: PushStrategy, session: Session) -> None:
        """未推送文章应允许 actionCard 推送."""
        article = _make_article(session)
        assert strategy.should_push(article, "actioncard") is True

    def test_actioncard_already_sent(self, strategy: PushStrategy, session: Session) -> None:
        """已通过 actionCard 推送的文章不再推送."""
        article = _make_article(session)
        session.add(
            PushLog(
                article_id=article.id,
                push_type="actioncard",
                pushed_at=datetime.now(),
            )
        )
        session.flush()
        assert strategy.should_push(article, "actioncard") is False

    def test_actioncard_daily_limit(self, strategy: PushStrategy, session: Session) -> None:
        """actionCard 每日上限."""
        # 创建 3 篇已 actionCard 推送的文章
        for i in range(DAILY_ACTIONCARD_LIMIT):
            art = _make_article(session, url=f"https://example.com/sent/{i}", title=f"Sent {i}")
            session.add(
                PushLog(
                    article_id=art.id,
                    push_type="actioncard",
                    pushed_at=datetime.now(),
                )
            )
        session.flush()

        # 新文章应被拒绝（已达上限）
        new_article = _make_article(session, url="https://example.com/new", title="New")
        assert strategy.should_push(new_article, "actioncard") is False

    def test_actioncard_below_daily_limit(self, strategy: PushStrategy, session: Session) -> None:
        """actionCard 未达每日上限."""
        # 只创建 1 篇已推送
        art = _make_article(session, url="https://example.com/sent", title="Sent")
        session.add(
            PushLog(
                article_id=art.id,
                push_type="actioncard",
                pushed_at=datetime.now(),
            )
        )
        session.flush()

        new_article = _make_article(session, url="https://example.com/new", title="New")
        assert strategy.should_push(new_article, "actioncard") is True


class TestDedup:
    """测试去重查询."""

    def test_is_actioncard_sent_false(self, strategy: PushStrategy, session: Session) -> None:
        """未推送过 actionCard."""
        article = _make_article(session)
        assert strategy._is_actioncard_sent(article.id) is False

    def test_is_actioncard_sent_true(self, strategy: PushStrategy, session: Session) -> None:
        """已推送过 actionCard."""
        article = _make_article(session)
        session.add(
            PushLog(
                article_id=article.id,
                push_type="actioncard",
                pushed_at=datetime.now(),
            )
        )
        session.flush()
        assert strategy._is_actioncard_sent(article.id) is True

    def test_is_feedcard_sent_false(self, strategy: PushStrategy, session: Session) -> None:
        """未推送过 feedCard."""
        article = _make_article(session)
        assert strategy.is_feedcard_sent(article.id) is False

    def test_is_feedcard_sent_true(self, strategy: PushStrategy, session: Session) -> None:
        """已推送过 feedCard."""
        article = _make_article(session)
        session.add(
            PushLog(
                article_id=article.id,
                push_type="feedcard",
                pushed_at=datetime.now(),
            )
        )
        session.flush()
        assert strategy.is_feedcard_sent(article.id) is True

    def test_actioncard_not_confused_with_feedcard(self, strategy: PushStrategy, session: Session) -> None:
        """feedCard 推送不影响 actionCard 去重."""
        article = _make_article(session)
        session.add(
            PushLog(
                article_id=article.id,
                push_type="feedcard",
                pushed_at=datetime.now(),
            )
        )
        session.flush()
        # feedCard 已推，但 actionCard 未推
        assert strategy.is_feedcard_sent(article.id) is True
        assert strategy._is_actioncard_sent(article.id) is False


class TestDailyCounter:
    """测试每日计数器."""

    def test_daily_count_zero(self, strategy: PushStrategy) -> None:
        """今日无 actionCard 推送."""
        assert strategy.daily_actioncard_count() == 0

    def test_daily_count_with_records(self, strategy: PushStrategy, session: Session) -> None:
        """今日有 actionCard 推送."""
        for i in range(2):
            art = _make_article(session, url=f"https://example.com/c/{i}", title=f"Count {i}")
            session.add(
                PushLog(
                    article_id=art.id,
                    push_type="actioncard",
                    pushed_at=datetime.now(),
                )
            )
        session.flush()
        assert strategy.daily_actioncard_count() == 2


class TestShouldSkipNoon:
    """测试午间跳过逻辑."""

    def test_skip_when_no_hot_articles(self, strategy: PushStrategy) -> None:
        """无热点文章时应跳过."""
        assert strategy.should_skip_noon() is True

    def test_no_skip_when_hot_articles(self, strategy: PushStrategy, session: Session) -> None:
        """有热点文章时不应跳过."""
        _make_article(
            session,
            url="https://example.com/hot",
            trend_score=9.0,
        )
        session.flush()
        assert strategy.should_skip_noon() is False

    def test_skip_when_below_threshold(self, strategy: PushStrategy, session: Session) -> None:
        """热点分数不够时仍跳过."""
        _make_article(
            session,
            url="https://example.com/warm",
            trend_score=7.5,
        )
        session.flush()
        assert strategy.should_skip_noon() is True


class TestArticleQueries:
    """测试文章查询函数."""

    def test_query_morning_articles(self, strategy: PushStrategy, session: Session) -> None:
        """晨报查询: Top N by trend_score."""
        for i in range(5):
            _make_article(
                session,
                url=f"https://example.com/m/{i}",
                title=f"Morning {i}",
                trend_score=float(i),
            )
        session.flush()

        articles = strategy.query_morning_articles(limit=3)
        assert len(articles) == 3
        # 应按 trend_score 降序
        assert articles[0].trend_score >= articles[1].trend_score

    def test_query_morning_excludes_sent(self, strategy: PushStrategy, session: Session) -> None:
        """晨报查询排除已推送文章."""
        _make_article(session, url="https://example.com/sent", dingtalk_sent=True)
        _make_article(session, url="https://example.com/unsent", trend_score=5.0)
        session.flush()

        articles = strategy.query_morning_articles()
        assert len(articles) == 1
        assert articles[0].url == "https://example.com/unsent"

    def test_query_evening_articles(self, strategy: PushStrategy, session: Session) -> None:
        """晚报查询: 今日增量文章."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        _make_article(
            session,
            url="https://example.com/today",
            fetched_at=today,
        )
        _make_article(
            session,
            url="https://example.com/yesterday",
            fetched_at=yesterday,
        )
        session.flush()

        articles = strategy.query_evening_articles()
        assert len(articles) == 1
        assert articles[0].url == "https://example.com/today"

    def test_query_noon_articles(self, strategy: PushStrategy, session: Session) -> None:
        """午间查询: trend_score >= 8."""
        _make_article(
            session,
            url="https://example.com/hot",
            trend_score=9.0,
        )
        _make_article(
            session,
            url="https://example.com/warm",
            trend_score=7.0,
        )
        session.flush()

        articles = strategy.query_noon_articles()
        assert len(articles) == 1
        assert articles[0].trend_score >= 8.0

    def test_query_trending_articles(self, strategy: PushStrategy, session: Session) -> None:
        """热点查询: trend_score >= 8, 未推送."""
        _make_article(
            session,
            url="https://example.com/hot",
            trend_score=9.0,
        )
        _make_article(
            session,
            url="https://example.com/hot_sent",
            trend_score=9.5,
            dingtalk_sent=True,
        )
        _make_article(
            session,
            url="https://example.com/warm",
            trend_score=7.0,
        )
        session.flush()

        articles = strategy.query_trending_articles()
        assert len(articles) == 1
        assert articles[0].url == "https://example.com/hot"

    def test_query_article_by_slug_url(self, strategy: PushStrategy, session: Session) -> None:
        """按 URL slug 查询文章."""
        _make_article(session, url="https://example.com/special-article")
        session.flush()

        result = strategy.query_article_by_slug("special-article")
        assert result is not None
        assert "special-article" in result.url

    def test_query_article_by_slug_title(self, strategy: PushStrategy, session: Session) -> None:
        """按标题 slug 查询文章."""
        _make_article(session, url="https://example.com/abc", title="Unique Title Here")
        session.flush()

        result = strategy.query_article_by_slug("Unique Title")
        assert result is not None

    def test_query_article_by_slug_not_found(self, strategy: PushStrategy) -> None:
        """slug 不存在."""
        result = strategy.query_article_by_slug("nonexistent")
        assert result is None


class TestWeeklyStats:
    """测试周报统计查询."""

    def test_query_weekly_stats(self, strategy: PushStrategy, session: Session) -> None:
        """查询本周统计数据."""
        _make_article(session, url="https://example.com/w1", category="LLM")
        _make_article(session, url="https://example.com/w2", category="CV")
        _make_article(session, url="https://example.com/w3", category="LLM")
        session.flush()

        stats = strategy.query_weekly_stats()
        assert stats["total"] == 3
        assert stats["categories"]["LLM"] == 2
        assert stats["categories"]["CV"] == 1

    def test_query_weekly_top(self, strategy: PushStrategy, session: Session) -> None:
        """查询本周 Top 文章."""
        for i in range(5):
            _make_article(
                session,
                url=f"https://example.com/top/{i}",
                trend_score=float(i),
            )
        session.flush()

        articles = strategy.query_weekly_top_articles(limit=3)
        assert len(articles) == 3
        assert articles[0].trend_score >= articles[1].trend_score
