"""测试数据库连接管理."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import SQLModel

from ainews.storage.database import (
    get_db_path, get_engine, init_db, get_session, reset_engine
)


@pytest.fixture(autouse=True)
def _reset():
    """每个测试前后重置引擎."""
    reset_engine()
    yield
    reset_engine()


class TestDatabase:
    """数据库管理测试."""

    def test_get_db_path(self) -> None:
        from ainews.config.settings import AppConfig
        path = get_db_path(AppConfig())
        assert path.name == "data.db"
        assert ".ainews" in str(path)

    def test_init_db_creates_file(self, tmp_path: Path) -> None:
        from ainews.config.settings import AppConfig
        config = AppConfig()
        config_dir = tmp_path / ".ainews"
        config_dir.mkdir()

        with patch("ainews.storage.database.get_db_path", return_value=config_dir / "data.db"):
            init_db()

        assert (config_dir / "data.db").exists()

    def test_init_db_creates_tables(self, tmp_path: Path) -> None:
        from ainews.config.settings import AppConfig
        config_dir = tmp_path / ".ainews"
        config_dir.mkdir()

        with patch("ainews.storage.database.get_db_path", return_value=config_dir / "data.db"):
            init_db()
            from sqlalchemy import inspect
            engine = get_engine()
            inspector = inspect(engine)
            tables = inspector.get_table_names()

        assert "articles" in tables
        assert "entities" in tables
        assert "fetch_log" in tables

    def test_get_session_context_manager(self, tmp_path: Path) -> None:
        from ainews.config.settings import AppConfig
        config_dir = tmp_path / ".ainews"
        config_dir.mkdir()

        with patch("ainews.storage.database.get_db_path", return_value=config_dir / "data.db"):
            init_db()
            with get_session() as session:
                assert session is not None

    def test_engine_singleton(self, tmp_path: Path) -> None:
        from ainews.config.settings import AppConfig
        config_dir = tmp_path / ".ainews"
        config_dir.mkdir()

        with patch("ainews.storage.database.get_db_path", return_value=config_dir / "data.db"):
            init_db()
            e1 = get_engine()
            e2 = get_engine()
            assert e1 is e2

    def test_reset_engine(self, tmp_path: Path) -> None:
        from ainews.config.settings import AppConfig
        config_dir = tmp_path / ".ainews"
        config_dir.mkdir()

        with patch("ainews.storage.database.get_db_path", return_value=config_dir / "data.db"):
            init_db()
            e1 = get_engine()
            reset_engine()
            from ainews.storage.database import _engine
            assert _engine is None
