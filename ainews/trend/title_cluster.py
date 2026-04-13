"""标题语义聚类：基于 SequenceMatcher 的相似度计算."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlmodel import Session, select

from ainews.storage.models import Article, Cluster

# 聚类相似度阈值（比 dedup 的 0.9 更宽松，用于跨源关联）
DEFAULT_CLUSTER_THRESHOLD = 0.8


def title_similarity(title_a: str, title_b: str) -> float:
    """计算两个标题的相似度.

    使用 difflib.SequenceMatcher 计算最长公共子序列比率。

    参数:
        title_a: 标题 A
        title_b: 标题 B

    返回:
        相似度分数 [0.0, 1.0]
    """
    if not title_a or not title_b:
        return 0.0

    # 统一空格和大小写后比较
    a = title_a.strip().lower()
    b = title_b.strip().lower()

    if a == b:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


def cluster_titles(
    session: Session,
    days: int = 1,
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
) -> list[dict]:
    """对指定时间范围内的文章执行标题聚类.

    参数:
        session: 数据库会话
        days: 聚类最近 N 天的文章
        threshold: 相似度阈值，默认 0.8

    返回:
        聚类列表，每个聚类 {"topic": str, "article_ids": list[int], "source_count": int}
    """
    since = datetime.utcnow() - timedelta(days=days)

    statement = (
        select(Article)
        .where(Article.status != "duplicate")
        .where(Article.title != "")
        .where(Article.fetched_at >= since)
        .order_by(Article.id)
    )
    articles = list(session.exec(statement).all())

    if not articles:
        return []

    # Union-Find 聚类
    parent: dict[int, int] = {a.id: a.id for a in articles}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    # N^2 比较
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            sim = title_similarity(articles[i].title, articles[j].title)
            if sim >= threshold:
                union(articles[i].id, articles[j].id)

    # 按根节点分组
    groups: dict[int, list[Article]] = {}
    for article in articles:
        root = find(article.id)
        groups.setdefault(root, []).append(article)

    # 过滤单文章组，构建聚类结果
    clusters: list[dict] = []
    for group_articles in groups.values():
        if len(group_articles) < 2:
            continue

        article_ids = [a.id for a in group_articles]
        sources = {a.source for a in group_articles if a.source}
        # 取最长的标题作为 topic
        topic = max(group_articles, key=lambda a: len(a.title)).title

        cluster_data = {
            "topic": topic,
            "article_ids": article_ids,
            "source_count": len(sources),
        }
        clusters.append(cluster_data)

    return clusters


def save_clusters(session: Session, clusters: list[dict]) -> int:
    """将聚类结果写入 clusters 表.

    参数:
        session: 数据库会话
        clusters: cluster_titles() 返回的聚类列表

    返回:
        写入的聚类数量
    """
    count = 0
    for cluster_data in clusters:
        cluster = Cluster(
            topic=cluster_data["topic"],
            article_ids=json.dumps(cluster_data["article_ids"]),
            source_count=cluster_data["source_count"],
            created_at=datetime.utcnow(),
        )
        session.add(cluster)
        count += 1

    if count > 0:
        session.commit()

    return count
