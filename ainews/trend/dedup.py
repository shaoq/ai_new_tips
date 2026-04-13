"""文章去重：基于标题相似度检测重复文章."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Sequence

from sqlmodel import Session, select

from ainews.storage.models import Article
from ainews.trend.title_cluster import title_similarity

# 默认去重相似度阈值
DEFAULT_DEDUP_THRESHOLD = 0.9


def dedup_articles(
    session: Session,
    days: int = 7,
    threshold: float = DEFAULT_DEDUP_THRESHOLD,
) -> list[tuple[int, int, float]]:
    """扫描未去重文章，通过标题相似度检测重复.

    参数:
        session: 数据库会话
        days: 扫描最近 N 天的文章
        threshold: 相似度阈值，默认 0.9

    返回:
        重复对列表 [(article_id_a, article_id_b, similarity), ...]
    """
    since = datetime.utcnow() - timedelta(days=days)

    statement = (
        select(Article)
        .where(Article.status != "duplicate")
        .where(Article.fetched_at >= since)
        .order_by(Article.id)
    )
    articles = list(session.exec(statement).all())

    duplicates: list[tuple[int, int, float]] = []

    # N^2 比较
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            a = articles[i]
            b = articles[j]
            sim = title_similarity(a.title, b.title)
            if sim >= threshold:
                duplicates.append((a.id, b.id, sim))

    # 标记后出现的文章为 duplicate（保留较早的文章）
    duplicate_ids: set[int] = set()
    for id_a, id_b, sim in duplicates:
        # id_a < id_b，标记后者为 duplicate
        if id_b not in duplicate_ids:
            article = session.get(Article, id_b)
            if article and article.status != "duplicate":
                article.status = "duplicate"
                session.add(article)
                duplicate_ids.add(id_b)

    if duplicate_ids:
        session.commit()

    return duplicates


def get_dedup_stats(session: Session) -> dict[str, int]:
    """获取去重统计信息.

    返回:
        {"total": 总文章数, "duplicate": 重复数, "unique": 唯一数}
    """
    total = len(session.exec(select(Article)).all())
    dup_count = len(
        session.exec(select(Article).where(Article.status == "duplicate")).all()
    )
    return {
        "total": total,
        "duplicate": dup_count,
        "unique": total - dup_count,
    }
