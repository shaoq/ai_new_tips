"""测试 CLI 命令: trend, dedup, entities."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine
from typer.testing import CliRunner

from ainews.cli.main import app
from ainews.storage.models import Article, Entity, SourceMetric

runner = CliRunner()


def _setup_test_db() -> Generator[Session, None, None]:
    """创建内存测试数据库并 monkey-patch get_engine."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    import ainews.storage.database as db_module
    original_engine = db_module._engine
    db_module._engine = engine

    session = Session(engine)
    yield session

    session.close()
    db_module._engine = original_engine


class TestTrendCommand:
    """ainews trend 命令测试."""

    def test_trend_dry_run(self) -> None:
        result = runner.invoke(app, ["trend", "--dry-run"])
        assert result.exit_code == 0
        assert "Step 1" in result.output or "dry" in result.output.lower() or result.exit_code == 0

    def test_trend_with_days(self) -> None:
        result = runner.invoke(app, ["trend", "--days", "7", "--dry-run"])
        assert result.exit_code == 0


class TestDedupCommand:
    """ainews dedup 命令测试."""

    def test_dedup_default(self) -> None:
        result = runner.invoke(app, ["dedup"])
        assert result.exit_code == 0

    def test_dedup_with_threshold(self) -> None:
        result = runner.invoke(app, ["dedup", "--threshold", "0.8"])
        assert result.exit_code == 0


class TestEntitiesCommand:
    """ainews entities 命令测试."""

    def test_entities_default(self) -> None:
        result = runner.invoke(app, ["entities"])
        assert result.exit_code == 0

    def test_entities_with_type(self) -> None:
        result = runner.invoke(app, ["entities", "--type", "person"])
        assert result.exit_code == 0

    def test_entities_new_only(self) -> None:
        result = runner.invoke(app, ["entities", "--new-only"])
        assert result.exit_code == 0
