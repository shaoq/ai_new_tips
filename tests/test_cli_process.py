"""CLI process 命令测试."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine
from typer.testing import CliRunner

from ainews.cli.process import app
from ainews.processor.processor import ProcessResult


runner = CliRunner()


def _make_article(session: Session, **overrides: object) -> int:
    """创建测试文章并返回 ID."""
    from ainews.storage.models import Article

    defaults = {
        "url": "https://example.com/test",
        "url_hash": "abc123",
        "title": "Test Article",
        "content_raw": "Content about AI",
        "source": "test",
        "source_name": "TestSource",
        "processed": False,
    }
    defaults.update(overrides)
    article = Article(**defaults)  # type: ignore[arg-type]
    session.add(article)
    session.commit()
    session.refresh(article)
    return article.id


VALID_LLM_RESPONSE = json.dumps({
    "category": "industry",
    "category_confidence": 0.95,
    "summary_zh": "这是一篇测试文章摘要。",
    "relevance": 9,
    "relevance_reason": "高度相关",
    "tags": ["ai", "gpt"],
    "entities": {
        "people": [],
        "companies": ["OpenAI"],
        "projects": [],
        "technologies": ["llm"],
    },
})


class TestProcessCommand:
    """ainews process 命令测试."""

    @patch("ainews.cli.process._create_processor")
    def test_process_unprocessed(self, mock_create: MagicMock) -> None:
        """无参数时处理未处理文章."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_unprocessed.return_value = [
            ProcessResult(
                article_id=1, success=True,
                category="industry", summary_zh="Summary",
                relevance=9, tags=["ai"],
            ),
            ProcessResult(
                article_id=2, success=True,
                category="research", summary_zh="Summary 2",
                relevance=7, tags=["ml"],
            ),
        ]

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        mock_processor.process_unprocessed.assert_called_once()
        assert "成功" in result.output
        mock_session.close.assert_called_once()

    @patch("ainews.cli.process._create_processor")
    def test_process_no_articles(self, mock_create: MagicMock) -> None:
        """无未处理文章."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_unprocessed.return_value = []

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "没有" in result.output

    @patch("ainews.cli.process._create_processor")
    def test_process_by_article_id(self, mock_create: MagicMock) -> None:
        """--article <id> 处理指定文章."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_by_id.return_value = ProcessResult(
            article_id=42, success=True,
            category="tools", summary_zh="A tool article",
            relevance=8, tags=["tool", "python"],
        )

        result = runner.invoke(app, ["--article", "42"])

        assert result.exit_code == 0
        mock_processor.process_by_id.assert_called_once_with(mock_session, 42)
        assert "处理成功" in result.output
        assert "tools" in result.output

    @patch("ainews.cli.process._create_processor")
    def test_process_by_article_id_not_found(self, mock_create: MagicMock) -> None:
        """--article <id> 文章不存在."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_by_id.return_value = None

        result = runner.invoke(app, ["--article", "999"])

        assert result.exit_code == 1
        assert "不存在" in result.output

    @patch("ainews.cli.process._create_processor")
    def test_process_by_article_id_failure(self, mock_create: MagicMock) -> None:
        """--article <id> 处理失败."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_by_id.return_value = ProcessResult(
            article_id=42, success=False, error="API error",
        )

        result = runner.invoke(app, ["--article", "42"])

        assert result.exit_code == 1
        assert "处理失败" in result.output

    @patch("ainews.cli.process._create_processor")
    def test_process_all_force(self, mock_create: MagicMock) -> None:
        """--all --force 强制全量处理."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_all_force.return_value = [
            ProcessResult(
                article_id=i, success=True,
                category="industry", summary_zh="Summary",
                relevance=8, tags=["ai"],
            )
            for i in range(1, 4)
        ]

        result = runner.invoke(app, ["--all", "--force"])

        assert result.exit_code == 0
        mock_processor.process_all_force.assert_called_once()
        assert "成功" in result.output

    @patch("ainews.cli.process._create_processor")
    def test_process_all_force_with_failures(self, mock_create: MagicMock) -> None:
        """--all --force 包含失败."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_all_force.return_value = [
            ProcessResult(
                article_id=1, success=True,
                category="industry", summary_zh="OK",
                relevance=8, tags=["ai"],
            ),
            ProcessResult(
                article_id=2, success=False, error="Rate limited",
            ),
        ]

        result = runner.invoke(app, ["--all", "--force"])

        assert result.exit_code == 0
        assert "失败" in result.output
        assert "Rate limited" in result.output

    @patch("ainews.cli.process._create_processor")
    def test_process_all_without_force_does_incremental(self, mock_create: MagicMock) -> None:
        """--all (without --force) 应该走增量处理."""
        mock_processor = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_create.return_value = (mock_processor, mock_session)

        mock_processor.process_unprocessed.return_value = []

        result = runner.invoke(app, ["--all"])

        assert result.exit_code == 0
        mock_processor.process_unprocessed.assert_called_once()
        mock_processor.process_all_force.assert_not_called()
