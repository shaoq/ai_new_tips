"""跨源关联引擎：整合 URL 匹配和标题聚类."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from ainews.storage.models import Article
from ainews.trend.title_cluster import cluster_titles, title_similarity
from ainews.trend.url_normalizer import normalize_url


class CrossSourceCorrelator:
    """跨源关联器：检测同一话题在不同平台的出现."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def correlate(
        self,
        days: int = 1,
        url_threshold: float = 1.0,
        title_threshold: float = 0.8,
    ) -> list[dict[str, Any]]:
        """对指定时间范围内的文章执行跨源关联.

        关联策略：
        1. URL 精确匹配（标准化后完全相同）
        2. 标题相似度匹配（> 0.8）

        参数:
            days: 分析最近 N 天的文章
            url_threshold: URL 匹配阈值（固定为 1.0，即精确匹配）
            title_threshold: 标题相似度阈值

        返回:
            关联组列表，每组包含:
            - article_ids: 关联的文章 ID 列表
            - platforms: 涉及的平台列表
            - match_type: "url" | "title" | "both"
        """
        since = datetime.utcnow() - timedelta(days=days)

        statement = (
            select(Article)
            .where(Article.status != "duplicate")
            .where(Article.fetched_at >= since)
            .order_by(Article.id)
        )
        articles = list(self.session.exec(statement).all())

        if not articles:
            return []

        # Step 1: URL 精确匹配分组
        url_groups: dict[str, list[Article]] = defaultdict(list)
        for article in articles:
            normalized = normalize_url(article.url)
            if normalized:
                url_groups[normalized].append(article)

        # Step 2: 标题相似度聚类
        title_clusters = cluster_titles(
            self.session, days=days, threshold=title_threshold
        )

        # Step 3: 合并关联结果
        # 记录每篇文章的关联组
        article_to_group: dict[int, int] = {}
        groups: list[dict[str, Any]] = []
        group_id = 0

        # 先处理 URL 匹配组
        for normalized_url, group_articles in url_groups.items():
            if len(group_articles) < 2:
                continue
            # 检查是否来自不同源
            sources = {a.source for a in group_articles}
            if len(sources) < 2:
                continue

            article_ids = [a.id for a in group_articles]
            platforms = sorted(sources)
            groups.append({
                "article_ids": article_ids,
                "platforms": platforms,
                "match_type": "url",
            })
            for aid in article_ids:
                article_to_group[aid] = group_id
            group_id += 1

        # 再处理标题聚类组（合并到已有组或创建新组）
        for cluster in title_clusters:
            cluster_ids = set(cluster["article_ids"])
            # 检查是否与已有组重叠
            merged = False
            for existing in groups:
                if set(existing["article_ids"]) & cluster_ids:
                    # 合并
                    merged_ids = list(set(existing["article_ids"]) | cluster_ids)
                    existing["article_ids"] = sorted(merged_ids)
                    # 更新 platforms
                    merged_articles = [
                        a for a in articles if a.id in set(merged_ids)
                    ]
                    existing["platforms"] = sorted(
                        {a.source for a in merged_articles if a.source}
                    )
                    existing["match_type"] = "both"
                    merged = True
                    break

            if not merged and cluster["source_count"] >= 2:
                article_objs = [
                    a for a in articles if a.id in cluster_ids
                ]
                platforms = sorted(
                    {a.source for a in article_objs if a.source}
                )
                if len(platforms) >= 2:
                    groups.append({
                        "article_ids": sorted(cluster_ids),
                        "platforms": platforms,
                        "match_type": "title",
                    })

        return groups

    def update_platforms(self, groups: list[dict[str, Any]]) -> int:
        """根据关联结果更新文章的 platforms 字段.

        参数:
            groups: correlate() 返回的关联组列表

        返回:
            更新的文章数量
        """
        updated = 0
        for group in groups:
            platforms = group["platforms"]
            for article_id in group["article_ids"]:
                article = self.session.get(Article, article_id)
                if article is None:
                    continue
                # 合并现有 platforms
                existing = json.loads(article.platforms) if article.platforms else []
                merged = sorted(set(existing + platforms))
                new_platforms_json = json.dumps(merged)
                if new_platforms_json != article.platforms:
                    article.platforms = new_platforms_json
                    self.session.add(article)
                    updated += 1

        if updated > 0:
            self.session.commit()

        return updated
