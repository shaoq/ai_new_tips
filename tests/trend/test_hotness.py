"""测试单源热度算法."""

from __future__ import annotations

import math

import pytest

from ainews.trend.hotness import (
    calculate_github_velocity,
    calculate_hf_hotness,
    calculate_hn_score,
    calculate_reddit_hot,
    get_platform_hotness,
    normalize_hf,
    normalize_hn,
    normalize_reddit,
    normalize_github,
    sigmoid_normalize,
)


class TestHNScore:
    """HN 排名算法测试."""

    def test_basic_score(self) -> None:
        score = calculate_hn_score(points=100, comment_count=10, hours_ago=1)
        assert score > 0

    def test_zero_points(self) -> None:
        score = calculate_hn_score(points=0, comment_count=0, hours_ago=1)
        assert score == 0.0

    def test_higher_points_higher_score(self) -> None:
        low = calculate_hn_score(points=10, comment_count=0, hours_ago=1)
        high = calculate_hn_score(points=100, comment_count=0, hours_ago=1)
        assert high > low

    def test_newer_posts_higher_score(self) -> None:
        new_post = calculate_hn_score(points=100, comment_count=0, hours_ago=0.5)
        old_post = calculate_hn_score(points=100, comment_count=0, hours_ago=24)
        assert new_post > old_post

    def test_comments_contribute(self) -> None:
        no_comments = calculate_hn_score(points=100, comment_count=0, hours_ago=1)
        with_comments = calculate_hn_score(points=100, comment_count=50, hours_ago=1)
        assert with_comments > no_comments

    def test_negative_hours_treated_as_zero(self) -> None:
        score = calculate_hn_score(points=100, comment_count=0, hours_ago=-5)
        assert score > 0

    def test_gravity_effect(self) -> None:
        score_low_gravity = calculate_hn_score(
            points=100, comment_count=0, hours_ago=10, gravity=1.0
        )
        score_high_gravity = calculate_hn_score(
            points=100, comment_count=0, hours_ago=10, gravity=2.5
        )
        assert score_low_gravity > score_high_gravity


class TestRedditHot:
    """Reddit Hot 算法测试."""

    def test_basic_score(self) -> None:
        score = calculate_reddit_hot(upvotes=100, downvotes=10, hours_ago=1)
        assert score > 0

    def test_more_upvotes_higher_score(self) -> None:
        low = calculate_reddit_hot(upvotes=10, downvotes=0, hours_ago=1)
        high = calculate_reddit_hot(upvotes=1000, downvotes=0, hours_ago=1)
        assert high > low

    def test_zero_votes(self) -> None:
        score = calculate_reddit_hot(upvotes=0, downvotes=0, hours_ago=1)
        assert score > 0  # Still has time component

    def test_downvotes_reduce_score(self) -> None:
        no_down = calculate_reddit_hot(upvotes=100, downvotes=0, hours_ago=1)
        with_down = calculate_reddit_hot(upvotes=100, downvotes=50, hours_ago=1)
        assert no_down > with_down


class TestHFHotness:
    """HuggingFace 热度测试."""

    def test_basic_hotness(self) -> None:
        score = calculate_hf_hotness(upvotes=50)
        assert score == 50.0

    def test_zero_upvotes(self) -> None:
        score = calculate_hf_hotness(upvotes=0)
        assert score == 0.0

    def test_comments_contribute(self) -> None:
        no_comments = calculate_hf_hotness(upvotes=50, comment_count=0)
        with_comments = calculate_hf_hotness(upvotes=50, comment_count=10)
        assert with_comments > no_comments

    def test_high_upvotes(self) -> None:
        score = calculate_hf_hotness(upvotes=500)
        assert score == 500.0


class TestGitHubVelocity:
    """GitHub Stars Velocity 测试."""

    def test_basic_velocity(self) -> None:
        vel = calculate_github_velocity(stars=1000, days_since_creation=30)
        assert vel > 0

    def test_zero_stars(self) -> None:
        vel = calculate_github_velocity(stars=0, days_since_creation=30)
        assert vel == 0.0

    def test_recent_stars_boost(self) -> None:
        no_recent = calculate_github_velocity(
            stars=1000, days_since_creation=30, recent_stars=0, recent_days=7
        )
        with_recent = calculate_github_velocity(
            stars=1000, days_since_creation=30, recent_stars=500, recent_days=7
        )
        assert with_recent > no_recent

    def test_zero_days(self) -> None:
        vel = calculate_github_velocity(stars=100, days_since_creation=0)
        assert vel > 0  # Treated as 1 day


class TestSigmoidNormalize:
    """Sigmoid 归一化测试."""

    def test_output_range(self) -> None:
        for value in [-100, 0, 25, 50, 75, 100, 1000]:
            result = sigmoid_normalize(value, midpoint=50.0)
            assert 0.0 <= result <= 1.0

    def test_at_midpoint(self) -> None:
        result = sigmoid_normalize(50.0, midpoint=50.0)
        assert abs(result - 0.5) < 0.01

    def test_above_midpoint(self) -> None:
        result = sigmoid_normalize(100.0, midpoint=50.0)
        assert result > 0.5

    def test_below_midpoint(self) -> None:
        result = sigmoid_normalize(0.0, midpoint=50.0)
        assert result < 0.5


class TestNormalizePlatform:
    """各平台归一化测试."""

    def test_normalize_hn_range(self) -> None:
        for score in [0, 1, 10, 50, 100, 500]:
            result = normalize_hn(score)
            assert 0.0 <= result <= 1.0

    def test_normalize_reddit_range(self) -> None:
        for score in [0, 50, 80, 100, 200]:
            result = normalize_reddit(score)
            assert 0.0 <= result <= 1.0

    def test_normalize_hf_range(self) -> None:
        for score in [0, 10, 20, 50, 100]:
            result = normalize_hf(score)
            assert 0.0 <= result <= 1.0

    def test_normalize_github_range(self) -> None:
        for score in [0, 10, 50, 100, 500]:
            result = normalize_github(score)
            assert 0.0 <= result <= 1.0


class TestGetPlatformHotness:
    """统一入口测试."""

    def test_hackernews(self) -> None:
        result = get_platform_hotness("hackernews", platform_score=100, hours_ago=1)
        assert 0.0 <= result <= 1.0

    def test_reddit(self) -> None:
        result = get_platform_hotness("reddit", upvote_count=100, hours_ago=1)
        assert 0.0 <= result <= 1.0

    def test_huggingface(self) -> None:
        result = get_platform_hotness("huggingface", upvote_count=50)
        assert 0.0 <= result <= 1.0

    def test_github(self) -> None:
        result = get_platform_hotness("github", stars=1000, days_since_creation=30)
        assert 0.0 <= result <= 1.0

    def test_unknown_source_with_score(self) -> None:
        result = get_platform_hotness("unknown", platform_score=100)
        assert 0.0 <= result <= 1.0

    def test_unknown_source_no_score(self) -> None:
        result = get_platform_hotness("unknown")
        assert result == 0.0

    def test_hn_alias(self) -> None:
        result = get_platform_hotness("hn", platform_score=100, hours_ago=1)
        assert result > 0.0
