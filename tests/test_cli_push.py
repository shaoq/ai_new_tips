"""测试 CLI push 命令."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine
from typer.testing import CliRunner

from ainews.cli.main import app
from ainews.storage.models import Article, PushLog
from ainews.config.settings import AppConfig, DingTalkConfig

runner = CliRunner()


@pytest.fixture
def engine():
    """创建内存 SQLite 引擎."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    """创建测试 Session."""
    with Session(engine) as s:
        yield s


def _make_config() -> AppConfig:
    """创建测试配置."""
    return AppConfig(
        dingtalk=DingTalkConfig(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test_token",
            secret="test_secret",
        ),
    )


def _make_article(
    session: Session,
    *,
    url: str = "https://example.com/1",
    title: str = "Test Article",
    trend_score: float = 5.0,
    processed: bool = True,
    fetched_at: datetime | None = None,
) -> Article:
    """创建测试文章."""
    article = Article(
        url=url,
        title=title,
        trend_score=trend_score,
        processed=processed,
        fetched_at=fetched_at or datetime.now(),
        source="hackernews",
        source_name="HackerNews",
    )
    session.add(article)
    session.flush()
    return article


class TestPushDingtalkTest:
    """测试 --test 选项."""

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.DingTalkClient")
    def test_test_option_success(self, mock_client_cls: MagicMock, mock_get_config: MagicMock) -> None:
        """--test 发送测试消息成功."""
        mock_get_config.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.send.return_value = {"errcode": 0}
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["push", "dingtalk", "--test"])
        assert result.exit_code == 0
        assert "成功" in result.output
        mock_client.send.assert_called_once()

    @patch("ainews.cli.push.get_config")
    def test_test_option_no_config(self, mock_get_config: MagicMock) -> None:
        """未配置钉钉时报错."""
        mock_get_config.return_value = AppConfig()

        result = runner.invoke(app, ["push", "dingtalk", "--test"])
        assert result.exit_code == 1
        assert "未配置" in result.output


class TestPushDingtalkWeekly:
    """测试 --weekly 选项."""

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.DingTalkClient")
    @patch("ainews.cli.push.get_session")
    def test_weekly_with_data(
        self,
        mock_get_session: MagicMock,
        mock_client_cls: MagicMock,
        mock_get_config: MagicMock,
        engine: Session,
    ) -> None:
        """--weekly 有数据时推送周报."""
        mock_get_config.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.send.return_value = {"errcode": 0}
        mock_client_cls.return_value = mock_client

        # 创建内存数据库 session
        test_engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(test_engine)

        with Session(test_engine) as session:
            _make_article(session, url="https://example.com/w1", trend_score=9.0)
            session.commit()

        def session_context():
            class _CtxMgr:
                def __enter__(self):
                    return Session(test_engine)
                def __exit__(self, *args):
                    pass
            return _CtxMgr()

        mock_get_session.return_value = session_context()

        result = runner.invoke(app, ["push", "dingtalk", "--weekly"])
        assert result.exit_code == 0

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.get_session")
    def test_weekly_no_data(self, mock_get_session: MagicMock, mock_get_config: MagicMock) -> None:
        """--weekly 无数据时跳过."""
        mock_get_config.return_value = _make_config()

        test_engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(test_engine)

        def session_context():
            class _CtxMgr:
                def __enter__(self):
                    return Session(test_engine)
                def __exit__(self, *args):
                    pass
            return _CtxMgr()

        mock_get_session.return_value = session_context()

        result = runner.invoke(app, ["push", "dingtalk", "--weekly"])
        assert "无文章" in result.output


class TestPushDingtalkTrending:
    """测试 --trending-only 选项."""

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.DingTalkClient")
    @patch("ainews.cli.push.get_session")
    def test_trending_with_articles(
        self,
        mock_get_session: MagicMock,
        mock_client_cls: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """--trending-only 有热点文章时推送."""
        mock_get_config.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.send.return_value = {"errcode": 0}
        mock_client_cls.return_value = mock_client

        test_engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(test_engine)

        with Session(test_engine) as session:
            _make_article(session, url="https://example.com/hot", trend_score=9.0)
            session.commit()

        def session_context():
            class _CtxMgr:
                def __enter__(self):
                    return Session(test_engine)
                def __exit__(self, *args):
                    pass
            return _CtxMgr()

        mock_get_session.return_value = session_context()

        result = runner.invoke(app, ["push", "dingtalk", "--trending-only"])
        assert result.exit_code == 0


class TestPushDingtalkArticle:
    """测试 --article 选项."""

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.DingTalkClient")
    @patch("ainews.cli.push.get_session")
    def test_article_found(
        self,
        mock_get_session: MagicMock,
        mock_client_cls: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """--article 找到文章时推送."""
        mock_get_config.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.send.return_value = {"errcode": 0}
        mock_client_cls.return_value = mock_client

        test_engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(test_engine)

        with Session(test_engine) as session:
            _make_article(session, url="https://example.com/my-article", title="My Article")
            session.commit()

        def session_context():
            class _CtxMgr:
                def __enter__(self):
                    return Session(test_engine)
                def __exit__(self, *args):
                    pass
            return _CtxMgr()

        mock_get_session.return_value = session_context()

        result = runner.invoke(app, ["push", "dingtalk", "--article", "my-article"])
        assert result.exit_code == 0

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.DingTalkClient")
    @patch("ainews.cli.push.get_session")
    def test_article_not_found(
        self,
        mock_get_session: MagicMock,
        mock_client_cls: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """--article 未找到文章时报错."""
        mock_get_config.return_value = _make_config()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        test_engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(test_engine)

        def session_context():
            class _CtxMgr:
                def __enter__(self):
                    return Session(test_engine)
                def __exit__(self, *args):
                    pass
            return _CtxMgr()

        mock_get_session.return_value = session_context()

        result = runner.invoke(app, ["push", "dingtalk", "--article", "nonexistent"])
        assert result.exit_code == 1
        assert "未找到" in result.output


class TestPushDingtalkFormat:
    """测试 --format 选项."""

    @patch("ainews.cli.push.get_config")
    @patch("ainews.cli.push.DingTalkClient")
    @patch("ainews.cli.push.get_session")
    def test_format_markdown_trending(
        self,
        mock_get_session: MagicMock,
        mock_client_cls: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """--format markdown 强制使用 markdown 格式."""
        mock_get_config.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.send.return_value = {"errcode": 0}
        mock_client_cls.return_value = mock_client

        test_engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(test_engine)

        with Session(test_engine) as session:
            _make_article(session, url="https://example.com/hot", trend_score=9.0)
            session.commit()

        def session_context():
            class _CtxMgr:
                def __enter__(self):
                    return Session(test_engine)
                def __exit__(self, *args):
                    pass
            return _CtxMgr()

        mock_get_session.return_value = session_context()

        result = runner.invoke(app, ["push", "dingtalk", "--trending-only", "--format", "markdown"])
        assert result.exit_code == 0
        # 验证发送的消息是 markdown 格式
        sent_message = mock_client.send.call_args[0][0]
        assert sent_message["msgtype"] == "markdown"
