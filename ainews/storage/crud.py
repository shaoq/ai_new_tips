"""CRUD 操作辅助函数."""

from __future__ import annotations

from typing import Any, TypeVar

from sqlmodel import Session, SQLModel, select

T = TypeVar("T", bound=SQLModel)


def get_or_create(
    session: Session,
    model: type[T],
    defaults: dict[str, Any] | None = None,
    **filters: Any,
) -> tuple[T, bool]:
    """查询记录，不存在则创建。返回 (instance, created)."""
    statement = select(model)
    for key, value in filters.items():
        statement = statement.where(getattr(model, key) == value)

    instance = session.exec(statement).first()
    if instance is not None:
        return instance, False

    data = {**filters}
    if defaults:
        data.update(defaults)
    instance = model(**data)
    session.add(instance)
    session.flush()
    return instance, True


def upsert(
    session: Session,
    model: type[T],
    filters: dict[str, Any],
    updates: dict[str, Any],
) -> T:
    """查询记录，存在则更新，不存在则创建."""
    statement = select(model)
    for key, value in filters.items():
        statement = statement.where(getattr(model, key) == value)

    instance = session.exec(statement).first()
    if instance is not None:
        for key, value in updates.items():
            setattr(instance, key, value)
        session.add(instance)
        session.flush()
        return instance

    data = {**filters, **updates}
    instance = model(**data)
    session.add(instance)
    session.flush()
    return instance


def bulk_insert(session: Session, instances: list[SQLModel]) -> None:
    """批量插入记录."""
    for instance in instances:
        session.add(instance)
    session.flush()
