"""测试 URL 标准化与 hash 计算."""

from __future__ import annotations

import pytest

from ainews.trend.url_normalizer import (
    compute_url_hash,
    normalize_url,
    urls_match,
)


class TestNormalizeUrl:
    """URL 标准化测试."""

    def test_basic_url(self) -> None:
        assert normalize_url("https://example.com/path") == "https://example.com/path"

    def test_remove_www(self) -> None:
        result = normalize_url("https://www.example.com/path")
        assert "www." not in result
        assert "example.com" in result

    def test_remove_trailing_slash(self) -> None:
        result = normalize_url("https://example.com/path/")
        assert not result.endswith("/path/")

    def test_root_path_kept(self) -> None:
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_empty_url(self) -> None:
        assert normalize_url("") == ""

    def test_whitespace_url(self) -> None:
        assert normalize_url("  https://example.com  ") == "https://example.com"

    def test_case_insensitive_hostname(self) -> None:
        result = normalize_url("https://EXAMPLE.COM/path")
        assert "example.com" in result.lower()

    def test_url_with_port(self) -> None:
        result = normalize_url("https://example.com:8080/path")
        assert ":8080" in result

    def test_url_with_fragment_removed(self) -> None:
        result = normalize_url("https://example.com/path#section")
        assert "#" not in result

    def test_multiple_trailing_slashes(self) -> None:
        result = normalize_url("https://example.com/path///")
        assert not result.endswith("///")

    def test_url_already_normalized(self) -> None:
        url = "https://example.com/path"
        assert normalize_url(url) == url

    def test_url_with_query_params_kept(self) -> None:
        result = normalize_url("https://example.com/search?q=ai&page=1")
        assert "q=ai" in result
        assert "page=1" in result

    def test_url_with_path_only(self) -> None:
        result = normalize_url("https://example.com/deep/nested/path")
        assert "deep/nested/path" in result


class TestComputeUrlHash:
    """URL hash 测试."""

    def test_same_url_same_hash(self) -> None:
        url = "https://example.com/path"
        assert compute_url_hash(url) == compute_url_hash(url)

    def test_different_url_different_hash(self) -> None:
        hash_a = compute_url_hash("https://example.com/a")
        hash_b = compute_url_hash("https://example.com/b")
        assert hash_a != hash_b

    def test_hash_is_sha256(self) -> None:
        result = compute_url_hash("https://example.com")
        assert len(result) == 64  # SHA256 hex digest length
        assert all(c in "0123456789abcdef" for c in result)

    def test_normalized_urls_same_hash(self) -> None:
        hash_a = compute_url_hash("https://example.com/path")
        hash_b = compute_url_hash("https://example.com/path/")
        assert hash_a == hash_b

    def test_www_urls_same_hash(self) -> None:
        hash_a = compute_url_hash("https://www.example.com/path")
        hash_b = compute_url_hash("https://example.com/path")
        assert hash_a == hash_b


class TestUrlsMatch:
    """URL 匹配测试."""

    def test_identical_urls(self) -> None:
        assert urls_match("https://example.com/a", "https://example.com/a")

    def test_different_urls(self) -> None:
        assert not urls_match("https://example.com/a", "https://example.com/b")

    def test_www_match(self) -> None:
        assert urls_match("https://www.example.com/a", "https://example.com/a")

    def test_trailing_slash_match(self) -> None:
        assert urls_match("https://example.com/a", "https://example.com/a/")

    def test_case_insensitive_match(self) -> None:
        assert urls_match("https://EXAMPLE.COM/a", "https://example.com/a")
