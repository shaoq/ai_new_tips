"""测试综合趋势评分."""

from __future__ import annotations

import pytest

from ainews.trend.scorer import (
    NOVELTY_BONUS_DEFAULT,
    NOVELTY_BONUS_WITH_NEW_ENTITY,
    TRENDING_THRESHOLD,
    calculate_cross_platform_bonus,
    calculate_trend_score,
)


class TestCalculateTrendScore:
    """综合趋势评分计算测试."""

    def test_zero_inputs(self) -> None:
        score = calculate_trend_score(0.0, 0.0, 0.0)
        assert score == 0.0

    def test_max_inputs_no_novelty(self) -> None:
        """Max inputs without novelty bonus = 9.0 (weights sum to 0.90)."""
        score = calculate_trend_score(1.0, 1.0, 1.0)
        assert score == 9.0

    def test_max_inputs_with_novelty(self) -> None:
        """Max inputs with novelty bonus = 10.8, clamped to 10.0."""
        score = calculate_trend_score(1.0, 1.0, 1.0, has_new_entity=True)
        assert score == 10.0

    def test_medium_inputs(self) -> None:
        score = calculate_trend_score(0.5, 0.5, 0.5)
        assert 0 < score < 10

    def test_novelty_bonus_with_new_entity(self) -> None:
        without = calculate_trend_score(0.5, 0.5, 0.5, has_new_entity=False)
        with_entity = calculate_trend_score(0.5, 0.5, 0.5, has_new_entity=True)
        assert with_entity > without

    def test_score_range(self) -> None:
        """评分应在 [0, 10] 范围内."""
        for ph in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for cp in [0.0, 0.25, 0.5, 0.75, 1.0]:
                for v in [0.0, 0.5, 1.0]:
                    score = calculate_trend_score(ph, cp, v)
                    assert 0.0 <= score <= 10.0

    def test_clamping_high(self) -> None:
        """即使所有输入为 1.0 + 新实体加成，也不超过 10."""
        score = calculate_trend_score(1.0, 1.0, 1.0, has_new_entity=True)
        assert score <= 10.0
        assert score == 10.0  # 9.0 * 1.2 = 10.8 clamped to 10

    def test_weights_sum(self) -> None:
        """权重之和应为 0.90 (platform*0.35 + cross_platform*0.35 + velocity*0.20)."""
        from ainews.trend.scorer import WEIGHT_CROSS_PLATFORM, WEIGHT_PLATFORM, WEIGHT_VELOCITY
        assert abs(WEIGHT_PLATFORM + WEIGHT_CROSS_PLATFORM + WEIGHT_VELOCITY - 0.90) < 0.001

    def test_platform_hotness_dominant(self) -> None:
        """当 platform_hotness 高但其他低时，分数应中等."""
        score = calculate_trend_score(1.0, 0.0, 0.0)
        assert score > 0
        assert score < 5  # 0.35 * 10 = 3.5


class TestCalculateCrossPlatformBonus:
    """跨平台加成测试."""

    def test_no_platforms(self) -> None:
        assert calculate_cross_platform_bonus([]) == 0.0

    def test_single_platform(self) -> None:
        assert calculate_cross_platform_bonus(["hn"]) == 0.2

    def test_two_platforms(self) -> None:
        assert calculate_cross_platform_bonus(["hn", "reddit"]) == 0.6

    def test_three_platforms(self) -> None:
        assert calculate_cross_platform_bonus(["hn", "reddit", "github"]) == 0.85

    def test_four_plus_platforms(self) -> None:
        assert calculate_cross_platform_bonus(["hn", "reddit", "github", "hf"]) == 1.0

    def test_five_platforms(self) -> None:
        assert calculate_cross_platform_bonus(["a", "b", "c", "d", "e"]) == 1.0


class TestTrendingThreshold:
    """趋势阈值测试."""

    def test_threshold_value(self) -> None:
        assert TRENDING_THRESHOLD == 6.0

    def test_below_threshold_not_trending(self) -> None:
        # platform=0.5, cross=0.2, velocity=0 -> ~2.45
        score = calculate_trend_score(0.5, 0.2, 0.0)
        assert score < TRENDING_THRESHOLD

    def test_above_threshold_is_trending(self) -> None:
        # platform=0.8, cross=0.85, velocity=0.8 -> ~8.55
        score = calculate_trend_score(0.8, 0.85, 0.8)
        assert score >= TRENDING_THRESHOLD
