"""综合趋势评分：多维度加权计算 trend_score."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from ainews.storage.models import Article, Cluster, Entity, SourceMetric
from ainews.trend.correlator import CrossSourceCorrelator
from ainews.trend.hotness import get_platform_hotness

# 综合评分权重
WEIGHT_PLATFORM = 0.35
WEIGHT_CROSS_PLATFORM = 0.35
WEIGHT_VELOCITY = 0.20

# 新实体加成
NOVELTY_BONUS_WITH_NEW_ENTITY = 1.2
NOVELTY_BONUS_DEFAULT = 1.0

# 趋势阈值
TRENDING_THRESHOLD = 6.0

# 评分级别
SCORE_LEVELS = {
    "low": (0, 4),
    "normal": (4, 6),
    "notable": (6, 8),
    "major": (8, 10),
}


def calculate_trend_score(
    platform_hotness: float,
    cross_platform_bonus: float,
    velocity: float,
    has_new_entity: bool = False,
) -> float:
    """计算综合趋势评分.

    公式:
        score = (platform_hotness * 0.35 + cross_platform_bonus * 0.35
                 + velocity * 0.20) * novelty_bonus * 10

    参数:
        platform_hotness: 单源热度 [0, 1]
        cross_platform_bonus: 跨平台加成 [0, 1]
        velocity: 增长速度 [0, 1]
        has_new_entity: 是否涉及新实体

    返回:
        trend_score [0.0, 10.0]
    """
    novelty_bonus = NOVELTY_BONUS_WITH_NEW_ENTITY if has_new_entity else NOVELTY_BONUS_DEFAULT

    raw = (
        platform_hotness * WEIGHT_PLATFORM
        + cross_platform_bonus * WEIGHT_CROSS_PLATFORM
        + velocity * WEIGHT_VELOCITY
    ) * novelty_bonus * 10.0

    # Clamp to [0, 10]
    return max(0.0, min(10.0, round(raw, 2)))


def calculate_velocity(session: Session, article_id: int) -> float:
    """从 source_metrics 表计算文章的增长速度（归一化到 [0, 1]）.

    使用 source_metrics 中的 velocity 字段，归一化到 [0, 1]。

    参数:
        session: 数据库会话
        article_id: 文章 ID

    返回:
        归一化速度 [0.0, 1.0]
    """
    statement = select(SourceMetric).where(
        SourceMetric.article_id == article_id
    )
    metrics = list(session.exec(statement).all())

    if not metrics:
        return 0.0

    # 取最大 velocity 并归一化
    max_velocity = max(m.velocity for m in metrics)
    # sigmoid 归一化，midpoint=10 表示 10 分/小时开始算快
    from ainews.trend.hotness import sigmoid_normalize
    return sigmoid_normalize(max_velocity, midpoint=10.0, steepness=0.2)


def determine_novelty_bonus(session: Session, article_id: int) -> float:
    """检查文章是否涉及新实体.

    参数:
        session: 数据库会话
        article_id: 文章 ID

    返回:
        1.2 如果涉及新实体，否则 1.0
    """
    article = session.get(Article, article_id)
    if article is None:
        return NOVELTY_BONUS_DEFAULT

    entities_json = article.entities
    if not entities_json:
        return NOVELTY_BONUS_DEFAULT

    try:
        entities_list = json.loads(entities_json)
    except (json.JSONDecodeError, TypeError):
        return NOVELTY_BONUS_DEFAULT

    if not isinstance(entities_list, list) or not entities_list:
        return NOVELTY_BONUS_DEFAULT

    # 检查是否有任何实体在 entities 表中标记为 is_new
    for entity_data in entities_list:
        if isinstance(entity_data, dict):
            name = entity_data.get("name", "")
        elif isinstance(entity_data, str):
            name = entity_data
        else:
            continue

        if not name:
            continue

        entity = session.exec(
            select(Entity).where(Entity.name == name)
        ).first()
        if entity and entity.is_new:
            return NOVELTY_BONUS_WITH_NEW_ENTITY

    return NOVELTY_BONUS_DEFAULT


def calculate_cross_platform_bonus(platforms: list[str]) -> float:
    """计算跨平台加成.

    出现的平台越多，加成越高。

    参数:
        platforms: 文章关联的平台列表

    返回:
        跨平台加成 [0.0, 1.0]
    """
    if not platforms:
        return 0.0

    count = len(platforms)
    if count == 1:
        return 0.2
    if count == 2:
        return 0.6
    if count == 3:
        return 0.85
    # 4+
    return 1.0


def update_trend_scores(
    session: Session,
    days: int = 1,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """对指定范围内的文章批量计算并更新 trend_score.

    参数:
        session: 数据库会话
        days: 分析最近 N 天的文章
        dry_run: 仅计算不写入

    返回:
        评分结果列表 [{"article_id": int, "trend_score": float, "is_trending": bool}, ...]
    """
    since = datetime.utcnow() - timedelta(days=days)

    statement = (
        select(Article)
        .where(Article.status != "duplicate")
        .where(Article.fetched_at >= since)
    )
    articles = list(session.exec(statement).all())

    results: list[dict[str, Any]] = []

    for article in articles:
        # 获取平台热度
        metrics = list(
            session.exec(
                select(SourceMetric).where(
                    SourceMetric.article_id == article.id
                )
            ).all()
        )

        if metrics:
            metric = metrics[0]
            hours_ago = 1.0
            if article.fetched_at:
                delta = datetime.utcnow() - article.fetched_at
                hours_ago = max(delta.total_seconds() / 3600, 0.1)

            platform_hotness = get_platform_hotness(
                source=article.source or metric.source,
                platform_score=metric.platform_score,
                comment_count=metric.comment_count,
                upvote_count=metric.upvote_count,
                hours_ago=hours_ago,
            )
        else:
            platform_hotness = 0.0

        # 跨平台加成
        platforms = json.loads(article.platforms) if article.platforms else []
        cross_platform_bonus = calculate_cross_platform_bonus(platforms)

        # 速度
        velocity = calculate_velocity(session, article.id)

        # 新实体检查
        novelty_bonus = determine_novelty_bonus(session, article.id)
        has_new_entity = novelty_bonus > NOVELTY_BONUS_DEFAULT

        # 计算综合分数
        trend_score = calculate_trend_score(
            platform_hotness=platform_hotness,
            cross_platform_bonus=cross_platform_bonus,
            velocity=velocity,
            has_new_entity=has_new_entity,
        )

        is_trending = trend_score >= TRENDING_THRESHOLD

        if not dry_run:
            article.trend_score = trend_score
            article.is_trending = is_trending
            session.add(article)

        results.append({
            "article_id": article.id,
            "title": article.title,
            "trend_score": trend_score,
            "is_trending": is_trending,
            "platform_hotness": round(platform_hotness, 3),
            "cross_platform_bonus": round(cross_platform_bonus, 3),
            "velocity": round(velocity, 3),
            "novelty_bonus": novelty_bonus,
        })

    if not dry_run and results:
        session.commit()

    return results
