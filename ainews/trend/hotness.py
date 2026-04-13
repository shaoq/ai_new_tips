"""单源热度算法：各平台的排名/热度计算与归一化."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ainews.storage.models import Article, SourceMetric


# ---------------------------------------------------------------------------
# HN 排名算法
# ---------------------------------------------------------------------------

HN_GRAVITY = 1.8


def calculate_hn_score(
    points: float,
    comment_count: int,
    hours_ago: float,
    gravity: float = HN_GRAVITY,
) -> float:
    """计算 Hacker News 排名分数.

    公式: (points + comment_count * 0.5) / (hours_ago + 2) ^ gravity

    参数:
        points: 得票数
        comment_count: 评论数
        hours_ago: 发布至今的小时数
        gravity: 重力因子，默认 1.8

    返回:
        HN 排名原始分数
    """
    if hours_ago < 0:
        hours_ago = 0
    numerator = points + comment_count * 0.5
    denominator = math.pow(hours_ago + 2, gravity)
    if denominator == 0:
        return 0.0
    return numerator / denominator


# ---------------------------------------------------------------------------
# Reddit Hot 算法
# ---------------------------------------------------------------------------

def calculate_reddit_hot(
    upvotes: int,
    downvotes: int,
    hours_ago: float,
) -> float:
    """计算 Reddit Hot 分数.

    公式: log10(max(|score|, 1)) + hours_since_epoch / 12.5
    score = upvotes - downvotes

    参数:
        upvotes: 赞成票数
        downvotes: 反对票数
        hours_ago: 发布至今的小时数

    返回:
        Reddit Hot 原始分数
    """
    score = upvotes - downvotes
    order = math.log10(max(abs(score), 1))
    # 使用相对时间（从发布时起算）
    # Reddit 使用 epoch 秒数/45000，我们用相对小时
    time_bonus = max(0, -hours_ago + 1000) / 12.5
    return round(order + time_bonus, 7)


# ---------------------------------------------------------------------------
# HuggingFace 分段阈值
# ---------------------------------------------------------------------------

def calculate_hf_hotness(
    upvotes: int,
    comment_count: int = 0,
) -> float:
    """计算 HuggingFace Papers 热度.

    基于 upvotes 的分段阈值。

    参数:
        upvotes: 赞成数
        comment_count: 评论数

    返回:
        HF 热度原始分数
    """
    base = upvotes + comment_count * 0.3
    return float(base)


# ---------------------------------------------------------------------------
# GitHub Stars Velocity
# ---------------------------------------------------------------------------

def calculate_github_velocity(
    stars: int,
    days_since_creation: float,
    recent_stars: int = 0,
    recent_days: int = 7,
) -> float:
    """计算 GitHub 仓库的 stars 增长速度.

    参数:
        stars: 总 stars 数
        days_since_creation: 仓库创建至今的天数
        recent_stars: 最近 N 天新增 stars 数
        recent_days: 最近 N 天的天数

    返回:
        速度分数（stars/天，考虑加速度）
    """
    if days_since_creation <= 0:
        days_since_creation = 1.0

    # 整体速度
    overall_velocity = stars / days_since_creation

    # 近期速度
    recent_velocity = recent_stars / max(recent_days, 1)

    # 加权组合：近期速度权重更高
    return recent_velocity * 0.7 + overall_velocity * 0.3


# ---------------------------------------------------------------------------
# Sigmoid 归一化
# ---------------------------------------------------------------------------

def sigmoid_normalize(value: float, midpoint: float = 50.0, steepness: float = 0.1) -> float:
    """Sigmoid-like 映射将原始分数归一化到 [0, 1].

    公式: 1 / (1 + exp(-steepness * (value - midpoint)))

    参数:
        value: 原始分数
        midpoint: sigmoid 中点（函数值=0.5 处）
        steepness: 陡峭度（越大越接近阶跃函数）

    返回:
        归一化分数 [0.0, 1.0]
    """
    exponent = -steepness * (value - midpoint)
    # 防止溢出
    exponent = max(min(exponent, 500), -500)
    return 1.0 / (1.0 + math.exp(exponent))


# ---------------------------------------------------------------------------
# 各平台归一化函数
# ---------------------------------------------------------------------------

def normalize_hn(raw_score: float) -> float:
    """归一化 HN 分数到 [0, 1].

    HN 分数范围大约 0~100+，midpoint=10 表示 10 分以上开始算热门。
    """
    return sigmoid_normalize(raw_score, midpoint=10.0, steepness=0.15)


def normalize_reddit(raw_score: float) -> float:
    """归一化 Reddit Hot 分数到 [0, 1]."""
    return sigmoid_normalize(raw_score, midpoint=80.0, steepness=0.2)


def normalize_hf(raw_score: float) -> float:
    """归一化 HF 热度到 [0, 1].

    HF upvotes 范围大约 0~200+，midpoint=20。
    """
    return sigmoid_normalize(raw_score, midpoint=20.0, steepness=0.15)


def normalize_github(raw_score: float) -> float:
    """归一化 GitHub 速度到 [0, 1].

    GitHub 速度范围差异大，midpoint=50 stars/天。
    """
    return sigmoid_normalize(raw_score, midpoint=50.0, steepness=0.1)


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

_PLATFORM_NORMALIZERS = {
    "hackernews": ("hn", normalize_hn),
    "reddit": ("reddit", normalize_reddit),
    "huggingface": ("hf", normalize_hf),
    "github": ("github", normalize_github),
}


def get_platform_hotness(
    source: str,
    platform_score: float = 0.0,
    comment_count: int = 0,
    upvote_count: int = 0,
    hours_ago: float = 0.0,
    stars: int = 0,
    days_since_creation: float = 1.0,
    recent_stars: int = 0,
) -> float:
    """根据 source 类型计算并归一化平台热度.

    参数:
        source: 数据源名称
        platform_score: 原始平台分数（points）
        comment_count: 评论数
        upvote_count: 赞成数
        hours_ago: 发布至今的小时数
        stars: GitHub stars 数
        days_since_creation: 仓库创建天数
        recent_stars: 近期新增 stars

    返回:
        归一化热度 [0.0, 1.0]
    """
    source_lower = source.lower()

    if source_lower == "hackernews" or source_lower == "hn":
        raw = calculate_hn_score(platform_score, comment_count, hours_ago)
        return normalize_hn(raw)

    if source_lower == "reddit":
        raw = calculate_reddit_hot(upvote_count, 0, hours_ago)
        return normalize_reddit(raw)

    if source_lower in ("huggingface", "hf"):
        raw = calculate_hf_hotness(upvote_count, comment_count)
        return normalize_hf(raw)

    if source_lower == "github":
        raw = calculate_github_velocity(
            stars, days_since_creation, recent_stars
        )
        return normalize_github(raw)

    # 未知源：使用 platform_score 直接归一化
    if platform_score > 0:
        return sigmoid_normalize(platform_score, midpoint=50.0, steepness=0.1)
    return 0.0
