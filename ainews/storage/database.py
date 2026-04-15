"""SQLite 数据库连接管理."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, text

from ainews.config.settings import AppConfig


def get_db_path(config: AppConfig | None = None) -> Path:
    """获取数据库文件路径."""
    if config is None:
        from ainews.config.loader import get_config
        config = get_config()
    return config.db_path


_engine = None


def get_engine(config: AppConfig | None = None):
    """获取数据库引擎（单例）."""
    global _engine
    if _engine is not None:
        return _engine

    db_path = get_db_path(config)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_path}"
    _engine = create_engine(db_url, echo=False)
    return _engine


def init_db(config: AppConfig | None = None) -> None:
    """初始化数据库：建表 + WAL 模式."""
    engine = get_engine(config)

    # WAL 模式
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

    # 建表（导入模型以注册表结构）
    import ainews.storage.models  # noqa: F401
    SQLModel.metadata.create_all(engine)

    # 增量迁移：为已有表添加新列
    _migrate_add_title_zh(engine)


@contextmanager
def get_session(config: AppConfig | None = None):
    """获取数据库 Session 上下文管理器."""
    engine = get_engine(config)
    with Session(engine) as session:
        yield session


def reset_engine() -> None:
    """重置引擎（仅用于测试）."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def _migrate_add_title_zh(engine) -> None:
    """为 articles 表添加 title_zh 列（幂等）."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN title_zh VARCHAR DEFAULT ''"))
            conn.commit()
    except Exception:
        # 列已存在时 SQLite 会报错，忽略即可
        logger.debug("title_zh 列已存在，跳过迁移")
