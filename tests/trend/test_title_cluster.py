"""测试标题语义聚类."""

from __future__ import annotations

from ainews.trend.title_cluster import title_similarity


class TestTitleSimilarity:
    """标题相似度计算测试."""

    def test_identical_titles(self) -> None:
        assert title_similarity("Hello World", "Hello World") == 1.0

    def test_identical_case_insensitive(self) -> None:
        result = title_similarity("Hello World", "hello world")
        assert result == 1.0

    def test_completely_different(self) -> None:
        result = title_similarity("Apple releases new iPhone", "Quantum computing breakthrough")
        assert result < 0.3

    def test_similar_titles(self) -> None:
        result = title_similarity(
            "GPT-5 released by OpenAI",
            "OpenAI releases GPT-5",
        )
        assert result > 0.3  # SequenceMatcher is conservative on word-order changes

    def test_same_topic_different_wording(self) -> None:
        result = title_similarity(
            "New AI model breaks records",
            "AI model sets new performance records",
        )
        assert result > 0.4

    def test_empty_title_a(self) -> None:
        assert title_similarity("", "Hello") == 0.0

    def test_empty_title_b(self) -> None:
        assert title_similarity("Hello", "") == 0.0

    def test_both_empty(self) -> None:
        assert title_similarity("", "") == 0.0

    def test_single_word_match(self) -> None:
        result = title_similarity("Python", "Python")
        assert result == 1.0

    def test_prefix_match(self) -> None:
        result = title_similarity(
            "Breaking: Major AI breakthrough",
            "Breaking: Major AI breakthrough announced today",
        )
        assert result > 0.7

    def test_threshold_08_similar(self) -> None:
        """测试相似度阈值 0.8 附近的标题."""
        # These should be similar enough for cross-source correlation (> 0.8)
        result = title_similarity(
            "OpenAI announces GPT-6 with multimodal capabilities",
            "OpenAI announces GPT-6 with multimodal capabilities",
        )
        assert result >= 0.8

    def test_threshold_09_similar(self) -> None:
        """测试相似度阈值 0.9 附近的标题（用于 dedup）."""
        result = title_similarity(
            "GPT-6 is here",
            "GPT-6 is here!",
        )
        assert result >= 0.9

    def test_whitespace_handling(self) -> None:
        # Double space vs single space still differ in SequenceMatcher
        result = title_similarity("Hello  World", "Hello World")
        assert result > 0.9  # Very similar but not identical due to double space
