"""测试 ObsidianClient: 健康检查、降级、重试、REST API 操作."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from ainews.publisher.obsidian_client import ObsidianClient


@pytest.fixture
def client(tmp_path: Path) -> ObsidianClient:
    """创建测试用 ObsidianClient."""
    return ObsidianClient(
        api_key="test-key-123",
        port=27124,
        vault_path=str(tmp_path),
        timeout=5.0,
    )


class TestObsidianClientInit:
    """客户端初始化测试."""

    def test_client_creation(self, tmp_path: Path) -> None:
        client = ObsidianClient(
            api_key="test-key",
            port=27124,
            vault_path=str(tmp_path),
        )
        assert not client.degraded
        assert client.vault_path == tmp_path

    def test_client_custom_port(self, tmp_path: Path) -> None:
        client = ObsidianClient(
            api_key="test-key",
            port=27125,
            vault_path=str(tmp_path),
        )
        assert client._base_url == "https://127.0.0.1:27125/v0"


class TestHealthCheck:
    """健康检查测试."""

    def test_health_check_success(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(200, request=httpx.Request("GET", "https://127.0.0.1:27124/v0/"))
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.health_check() is True
            assert not client.degraded

    def test_health_check_connection_error(self, client: ObsidianClient) -> None:
        with patch.object(
            client._client, "request", side_effect=httpx.ConnectError("refused")
        ):
            assert client.health_check() is False
            assert client.degraded is True

    def test_health_check_timeout(self, client: ObsidianClient) -> None:
        with patch.object(
            client._client, "request", side_effect=httpx.TimeoutException("timeout")
        ):
            assert client.health_check() is False
            assert client.degraded is True

    def test_health_check_500(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(500, request=httpx.Request("GET", "https://127.0.0.1:27124/v0/"))
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.health_check() is False
            assert client.degraded is True


class TestDegradedMode:
    """降级模式测试."""

    def test_degraded_mode_file_write(self, client: ObsidianClient, tmp_path: Path) -> None:
        client._degraded = True
        success = client.put_vault_file("AI-News/test.md", "# Hello")
        assert success is True
        content = (tmp_path / "AI-News" / "test.md").read_text()
        assert content == "# Hello"

    def test_degraded_mode_file_read(self, client: ObsidianClient, tmp_path: Path) -> None:
        client._degraded = True
        test_file = tmp_path / "AI-News" / "test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("content")
        result = client.get_vault_file("AI-News/test.md")
        assert result == "content"

    def test_degraded_mode_file_read_not_found(self, client: ObsidianClient) -> None:
        client._degraded = True
        result = client.get_vault_file("nonexistent.md")
        assert result is None

    def test_degraded_mode_creates_directories(self, client: ObsidianClient, tmp_path: Path) -> None:
        client._degraded = True
        client.put_vault_file("AI-News/Industry/2026-01-01-test.md", "content")
        assert (tmp_path / "AI-News" / "Industry" / "2026-01-01-test.md").exists()


class TestRestApiOperations:
    """REST API 操作测试."""

    def test_put_vault_file_success(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(204, request=httpx.Request("PUT", "https://127.0.0.1:27124/v0/vault/test.md"))
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.put_vault_file("test.md", "content") is True

    def test_put_vault_file_failure(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(500, request=httpx.Request("PUT", "https://127.0.0.1:27124/v0/vault/test.md"))
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.put_vault_file("test.md", "content") is False

    def test_get_vault_file_success(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(
            200, text="file content", request=httpx.Request("GET", "https://127.0.0.1:27124/v0/vault/test.md")
        )
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.get_vault_file("test.md") == "file content"

    def test_get_vault_file_not_found(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(404, request=httpx.Request("GET", "https://127.0.0.1:27124/v0/vault/test.md"))
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.get_vault_file("test.md") is None

    def test_patch_periodic_daily_success(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(
            204, request=httpx.Request("PATCH", "https://127.0.0.1:27124/v0/periodic/daily/")
        )
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.patch_periodic_daily("heading", "content") is True

    def test_patch_periodic_daily_degraded(self, client: ObsidianClient) -> None:
        client._degraded = True
        assert client.patch_periodic_daily("heading", "content") is False

    def test_patch_frontmatter_success(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(
            204, request=httpx.Request("PATCH", "https://127.0.0.1:27124/v0/vault/test.md")
        )
        with patch.object(client._client, "request", return_value=mock_response):
            assert client.patch_frontmatter("test.md", {"trend_score": 8.0}) is True

    def test_patch_frontmatter_degraded(self, client: ObsidianClient) -> None:
        client._degraded = True
        assert client.patch_frontmatter("test.md", {"trend_score": 8.0}) is False

    def test_search_simple_success(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(
            200,
            json=[{"path": "test.md", "filename": "test"}],
            request=httpx.Request("POST", "https://127.0.0.1:27124/v0/search/simple/"),
        )
        with patch.object(client._client, "request", return_value=mock_response):
            results = client.search_simple("test")
            assert len(results) == 1

    def test_search_simple_failure(self, client: ObsidianClient) -> None:
        mock_response = httpx.Response(500, request=httpx.Request("POST", "https://127.0.0.1:27124/v0/search/simple/"))
        with patch.object(client._client, "request", return_value=mock_response):
            results = client.search_simple("test")
            assert results == []


class TestRetry:
    """重试机制测试."""

    def test_retry_on_connection_error(self, client: ObsidianClient) -> None:
        call_count = 0

        def mock_request(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.ConnectError("refused")
            return httpx.Response(200, request=httpx.Request("GET", "https://127.0.0.1:27124/v0/"))

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("ainews.publisher.obsidian_client.time.sleep"):
                result = client._request("GET", "/")
                assert result.status_code == 200
                assert call_count == 3

    def test_retry_exhausted(self, client: ObsidianClient) -> None:
        with patch.object(
            client._client, "request", side_effect=httpx.ConnectError("refused")
        ):
            with patch("ainews.publisher.obsidian_client.time.sleep"):
                with pytest.raises(httpx.ConnectError):
                    client._request("GET", "/")

    def test_no_retry_on_4xx(self, client: ObsidianClient) -> None:
        call_count = 0

        def mock_request(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, request=httpx.Request("GET", "https://127.0.0.1:27124/v0/"))

        with patch.object(client._client, "request", side_effect=mock_request):
            result = client._request("GET", "/")
            assert result.status_code == 404
            assert call_count == 1


class TestContextManager:
    """上下文管理器测试."""

    def test_context_manager(self, tmp_path: Path) -> None:
        with ObsidianClient(api_key="test", vault_path=str(tmp_path)) as client:
            assert client is not None
        # client should be closed after exit

    def test_fs_search(self, client: ObsidianClient, tmp_path: Path) -> None:
        client._degraded = True
        test_file = tmp_path / "AI-News" / "Entities" / "Sam-Altman.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("content")
        results = client.search_simple("Sam-Altman")
        assert len(results) == 1
        assert "Sam-Altman" in results[0]["filename"]
