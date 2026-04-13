"""自动发现机制：新兴研究员、新 AI 项目、新公司."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from ainews.storage.models import Article, Entity

logger = logging.getLogger(__name__)


def discover_emerging_researchers(
    session: Session,
    days: int = 30,
) -> list[dict[str, Any]]:
    """发现新兴研究员：追踪 ArXiv 文章作者的引用加速度.

    简化版：从近期文章的 person 实体中，统计出现频次，
    首次出现在近期窗口内的标记为 emerging_researcher。

    参数:
        session: 数据库会话
        days: 分析窗口天数

    返回:
        新兴研究员列表 [{"name": str, "mention_count": int, "first_seen": datetime}, ...]
    """
    since = datetime.utcnow() - timedelta(days=days)

    # 查找近期出现且类型为 person 的新实体
    statement = (
        select(Entity)
        .where(Entity.type == "person")
        .where(Entity.is_new == True)  # noqa: E712
        .where(Entity.first_seen_at >= since)
        .order_by(Entity.mention_count.desc())
    )
    new_persons = list(session.exec(statement).all())

    researchers: list[dict[str, Any]] = []
    for person in new_persons:
        researchers.append({
            "name": person.name,
            "mention_count": person.mention_count,
            "first_seen": person.first_seen_at.isoformat() if person.first_seen_at else None,
        })

    return researchers


def discover_new_projects(
    session: Session,
    days: int = 7,
    min_hn_points: int = 50,
    min_github_stars: int = 500,
) -> list[dict[str, Any]]:
    """发现新 AI 项目：Show HN 高分帖子 + GitHub 快速增长仓库.

    参数:
        session: 数据库会话
        days: 分析窗口天数
        min_hn_points: HN 最低分数阈值
        min_github_stars: GitHub 最低 stars 阈值

    返回:
        新项目列表 [{"name": str, "sources": list[str], "score": float}, ...]
    """
    since = datetime.utcnow() - timedelta(days=days)

    # 查找 project 类型的新实体
    statement = (
        select(Entity)
        .where(Entity.type == "project")
        .where(Entity.is_new == True)  # noqa: E712
        .where(Entity.first_seen_at >= since)
    )
    new_projects = list(session.exec(statement).all())

    projects: list[dict[str, Any]] = []
    for proj in new_projects:
        # 查找关联的文章以验证来源
        from ainews.storage.models import ArticleEntity
        links = list(
            session.exec(
                select(ArticleEntity).where(ArticleEntity.entity_id == proj.id)
            ).all()
        )

        sources: set[str] = set()
        for link in links:
            article = session.get(Article, link.article_id)
            if article:
                sources.add(article.source)

        # 检查是否满足交叉验证条件
        score = 0.0
        if "hackernews" in sources:
            score += 0.5
        if "github" in sources:
            score += 0.5

        if score >= 0.5:
            projects.append({
                "name": proj.name,
                "sources": sorted(sources),
                "score": score,
            })

    return projects


def discover_new_companies(
    session: Session,
    days: int = 30,
) -> list[dict[str, Any]]:
    """发现新公司：从 LLM 提取的 company 实体中检测首次出现的公司.

    参数:
        session: 数据库会话
        days: 分析窗口天数

    返回:
        新公司列表 [{"name": str, "mention_count": int, "first_seen": str}, ...]
    """
    since = datetime.utcnow() - timedelta(days=days)

    statement = (
        select(Entity)
        .where(Entity.type == "company")
        .where(Entity.is_new == True)  # noqa: E712
        .where(Entity.first_seen_at >= since)
        .order_by(Entity.mention_count.desc())
    )
    new_companies = list(session.exec(statement).all())

    companies: list[dict[str, Any]] = []
    for company in new_companies:
        companies.append({
            "name": company.name,
            "mention_count": company.mention_count,
            "first_seen": company.first_seen_at.isoformat() if company.first_seen_at else None,
        })

    return companies


def run_auto_discovery(
    session: Session,
    days: int = 7,
) -> dict[str, list[dict[str, Any]]]:
    """运行完整的自动发现流程.

    参数:
        session: 数据库会话
        days: 分析窗口天数

    返回:
        {"researchers": [...], "projects": [...], "companies": [...]}
    """
    researchers = discover_emerging_researchers(session, days=days)
    projects = discover_new_projects(session, days=days)
    companies = discover_new_companies(session, days=days)

    logger.info(
        "Auto-discovery: %d researchers, %d projects, %d companies",
        len(researchers),
        len(projects),
        len(companies),
    )

    return {
        "researchers": researchers,
        "projects": projects,
        "companies": companies,
    }
