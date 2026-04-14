"""测试 HuggingFace Papers 采集器 — REST API、论文规范化、upvotes 过滤、水印逻辑."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ainews.config.settings import HFPapersConfig
from ainews.fetcher.hf_papers import HF_PAPERS_API, HFPapersFetcher


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def hf_config() -> HFPapersConfig:
    """默认 HFPapersConfig (min_upvotes=10)."""
    return HFPapersConfig(enabled=True, min_upvotes=10)


@pytest.fixture
def fetcher(hf_config: HFPapersConfig) -> HFPapersFetcher:
    """构造 HFPapersFetcher 并替换 httpx.Client 为 mock."""
    f = HFPapersFetcher(config=hf_config)
    f._client = MagicMock(spec=httpx.Client)
    return f


def _make_paper(
    paper_id: str = "2404.12345",
    title: str = "Test Paper Title",
    abstract: str = "This is a test abstract.",
    authors: list[dict[str, str]] | None = None,
    upvotes: int = 20,
    published_at: str = "2026-04-14T10:00:00Z",
) -> dict[str, Any]:
    """构造一条模拟的 HF Paper API 响应."""
    if authors is None:
        authors = [{"name": "Alice Smith"}, {"name": "Bob Lee"}]
    return {
        "paper": {
            "id": paper_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "upvotes": upvotes,
        },
        "publishedAt": published_at,
    }


def _make_response(
    status_code: int = 200,
    json_data: Any = None,
) -> MagicMock:
    """构造 mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or []
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ------------------------------------------------------------------
# 测试 _normalize
# ------------------------------------------------------------------


class TestNormalize:
    def test_basic_normalization(self, fetcher: HFPapersFetcher) -> None:
        """基本规范化：映射字段到统一格式."""
        paper = _make_paper()
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["url"] == "https://huggingface.co/papers/2404.12345"
        assert result["title"] == "Test Paper Title"
        assert result["content_raw"] == "This is a test abstract."
        assert result["source"] == "hf_papers"
        assert result["source_name"] == "HuggingFace Papers"
        assert result["author"] == "Alice Smith, Bob Lee"
        assert result["metrics"]["upvote_count"] == 20
        assert result["metrics"]["platform_score"] == 20.0

    def test_published_at_parsed(self, fetcher: HFPapersFetcher) -> None:
        """publishedAt 解析为 datetime 对象."""
        paper = _make_paper(published_at="2026-04-14T08:30:00Z")
        result = fetcher._normalize(paper)

        assert result is not None
        assert isinstance(result["published_at"], datetime)
        assert result["published_at"].year == 2026
        assert result["published_at"].month == 4
        assert result["published_at"].day == 14

    def test_published_at_with_offset(self, fetcher: HFPapersFetcher) -> None:
        """publishedAt 带时区偏移."""
        paper = _make_paper(published_at="2026-04-14T08:30:00+05:30")
        result = fetcher._normalize(paper)

        assert result is not None
        assert isinstance(result["published_at"], datetime)

    def test_published_at_missing(self, fetcher: HFPapersFetcher) -> None:
        """缺少 publishedAt 时 published_at 为 None."""
        paper = _make_paper()
        del paper["publishedAt"]
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["published_at"] is None
        assert result["time"] == ""

    def test_published_at_invalid(self, fetcher: HFPapersFetcher) -> None:
        """无效的 publishedAt 格式不崩溃，published_at 为 None."""
        paper = _make_paper(published_at="not-a-date")
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["published_at"] is None

    def test_empty_paper_info_returns_none(self, fetcher: HFPapersFetcher) -> None:
        """paper 字段为空时返回 None."""
        result = fetcher._normalize({"paper": {}, "publishedAt": "2026-04-14T10:00:00Z"})
        assert result is None

    def test_missing_paper_key_returns_none(self, fetcher: HFPapersFetcher) -> None:
        """缺少 paper 键时返回 None."""
        result = fetcher._normalize({"publishedAt": "2026-04-14T10:00:00Z"})
        assert result is None

    def test_missing_paper_id_returns_none(self, fetcher: HFPapersFetcher) -> None:
        """paper.id 为空时返回 None."""
        paper = _make_paper()
        paper["paper"]["id"] = ""
        result = fetcher._normalize(paper)
        assert result is None

    def test_authors_as_strings(self, fetcher: HFPapersFetcher) -> None:
        """authors 列表中的元素为字符串而非 dict."""
        paper = _make_paper()
        paper["paper"]["authors"] = ["Alice Smith", "Bob Lee"]
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["author"] == "Alice Smith, Bob Lee"

    def test_empty_authors_list(self, fetcher: HFPapersFetcher) -> None:
        """authors 为空列表."""
        paper = _make_paper()
        paper["paper"]["authors"] = []
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["author"] == ""

    def test_zero_upvotes(self, fetcher: HFPapersFetcher) -> None:
        """upvotes 为 0 的论文."""
        paper = _make_paper(upvotes=0)
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["metrics"]["upvote_count"] == 0
        assert result["metrics"]["platform_score"] == 0.0

    def test_missing_upvotes_defaults_to_zero(self, fetcher: HFPapersFetcher) -> None:
        """缺少 upvotes 字段默认为 0."""
        paper = _make_paper()
        del paper["paper"]["upvotes"]
        result = fetcher._normalize(paper)

        assert result is not None
        assert result["metrics"]["upvote_count"] == 0


# ------------------------------------------------------------------
# 测试 fetch_items
# ------------------------------------------------------------------


class TestFetchItems:
    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_basic_fetch(self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher) -> None:
        """基本单日拉取流程."""
        papers = [
            _make_paper(paper_id="2404.001", upvotes=50),
            _make_paper(paper_id="2404.002", upvotes=30),
            _make_paper(paper_id="2404.003", upvotes=5),  # 低于 min_upvotes=10
        ]
        fetcher._client.get.return_value = _make_response(json_data=papers)

        items = fetcher.fetch_items()

        assert fetcher._client.get.called
        # 2 篇 upvotes >= 10，1 篇被过滤
        assert len(items) == 2
        assert items[0]["url"] == "https://huggingface.co/papers/2404.001"
        assert items[1]["url"] == "https://huggingface.co/papers/2404.002"

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_empty_response(self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher) -> None:
        """API 返回空列表."""
        fetcher._client.get.return_value = _make_response(json_data=[])

        items = fetcher.fetch_items()

        assert items == []

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_with_since(self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher) -> None:
        """增量拉取：since 参数决定回填天数."""
        papers = [_make_paper(paper_id="2404.001", upvotes=20)]
        fetcher._client.get.return_value = _make_response(json_data=papers)

        # since 设为 3 天前，应拉取 3 天
        since_date = "2026-04-11"
        items = fetcher.fetch_items(since=since_date)

        # get 应被调用多次（每天一次）
        assert fetcher._client.get.call_count >= 1
        assert len(items) >= 1

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_with_invalid_since(self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher) -> None:
        """since 格式无效时回退为 1 天."""
        papers = [_make_paper(upvotes=20)]
        fetcher._client.get.return_value = _make_response(json_data=papers)

        items = fetcher.fetch_items(since="not-a-date")

        # 只调用 1 次（回退为 1 天）
        assert fetcher._client.get.call_count == 1

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_with_backfill_days(self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher) -> None:
        """显式 backfill_days 参数."""
        papers = [_make_paper(upvotes=20)]
        fetcher._client.get.return_value = _make_response(json_data=papers)

        items = fetcher.fetch_items(backfill_days=3)

        # 3 天，每天一次请求
        assert fetcher._client.get.call_count == 3

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_429_retry(self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher) -> None:
        """429 速率限制触发重试."""
        papers = [_make_paper(upvotes=20)]
        error_resp = _make_response(status_code=429)
        success_resp = _make_response(json_data=papers)

        # 第一次 429，第二次成功
        fetcher._client.get.side_effect = [error_resp, success_resp]

        with patch("ainews.fetcher.hf_papers.time.sleep") as mock_sleep:
            items = fetcher.fetch_items()

        assert len(items) == 1
        # 确认退避 sleep 被调用
        mock_sleep.assert_called_once_with(30)

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_non_429_http_error_logged(
        self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher
    ) -> None:
        """非 429 HTTP 错误被记录但不会重试."""
        error_resp = _make_response(status_code=500)

        fetcher._client.get.return_value = error_resp

        items = fetcher.fetch_items()

        # 不崩溃，返回空列表（被过滤后）
        assert items == []

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_fetch_generic_exception_logged(
        self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher
    ) -> None:
        """通用异常被记录但不崩溃."""
        fetcher._client.get.side_effect = Exception("unexpected failure")

        items = fetcher.fetch_items()

        assert items == []


# ------------------------------------------------------------------
# 测试 upvotes 过滤
# ------------------------------------------------------------------


class TestUpvotesFilter:
    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_filter_by_min_upvotes(
        self, mock_rate_limit: MagicMock, fetcher: HFPapersFetcher
    ) -> None:
        """仅保留 upvotes >= min_upvotes 的论文."""
        papers = [
            _make_paper(paper_id="2404.001", upvotes=100),
            _make_paper(paper_id="2404.002", upvotes=10),   # 等于阈值
            _make_paper(paper_id="2404.003", upvotes=9),    # 低于阈值
            _make_paper(paper_id="2404.004", upvotes=0),    # 0
        ]
        fetcher._client.get.return_value = _make_response(json_data=papers)

        items = fetcher.fetch_items()

        # min_upvotes=10，保留 100 和 10
        assert len(items) == 2
        assert items[0]["metrics"]["upvote_count"] == 100
        assert items[1]["metrics"]["upvote_count"] == 10

    @patch.object(HFPapersFetcher, "_rate_limit")
    def test_no_filter_when_min_upvotes_zero(
        self, mock_rate_limit: MagicMock
    ) -> None:
        """min_upvotes=0 时不过滤."""
        config = HFPapersConfig(enabled=True, min_upvotes=0)
        f = HFPapersFetcher(config=config)
        f._client = MagicMock(spec=httpx.Client)

        papers = [
            _make_paper(paper_id="2404.001", upvotes=0),
            _make_paper(paper_id="2404.002", upvotes=5),
        ]
        f._client.get.return_value = _make_response(json_data=papers)

        items = f.fetch_items()

        assert len(items) == 2


# ------------------------------------------------------------------
# 测试 _build_cursor
# ------------------------------------------------------------------


class TestBuildCursor:
    def test_returns_max_date(self, fetcher: HFPapersFetcher) -> None:
        """返回最大的 published_at 日期字符串."""
        items = [
            {
                "published_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            },
            {
                "published_at": datetime(2026, 4, 14, 8, 0, 0, tzinfo=timezone.utc),
            },
            {
                "published_at": datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc),
            },
        ]
        cursor = fetcher._build_cursor(items)

        assert cursor == "2026-04-14"

    def test_empty_items_returns_none(self, fetcher: HFPapersFetcher) -> None:
        """空列表返回 None."""
        cursor = fetcher._build_cursor([])
        assert cursor is None

    def test_items_without_published_at(self, fetcher: HFPapersFetcher) -> None:
        """所有条目缺少 published_at 时返回 None."""
        items = [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor is None

    def test_mixed_with_and_without_published_at(
        self, fetcher: HFPapersFetcher
    ) -> None:
        """混合有和没有 published_at 的条目，只取有值的."""
        items = [
            {"url": "https://example.com/1"},
            {
                "published_at": datetime(2026, 4, 13, 10, 0, 0, tzinfo=timezone.utc),
            },
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-13"

    def test_string_published_at(self, fetcher: HFPapersFetcher) -> None:
        """published_at 为字符串时截取前 10 位（日期部分）."""
        items = [
            {"published_at": "2026-04-12T10:00:00"},
            {"published_at": "2026-04-14T08:00:00"},
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-14"

    def test_single_item(self, fetcher: HFPapersFetcher) -> None:
        """单条记录返回其日期."""
        items = [
            {
                "published_at": datetime(2026, 4, 14, 15, 30, 0, tzinfo=timezone.utc),
            },
        ]
        cursor = fetcher._build_cursor(items)
        assert cursor == "2026-04-14"


# ------------------------------------------------------------------
# 测试 rate limiting
# ------------------------------------------------------------------


class TestRateLimit:
    def test_rate_limit_sleeps_when_too_soon(self, fetcher: HFPapersFetcher) -> None:
        """请求间隔不足 2s 时触发 sleep."""
        fetcher._last_request_time = 1000.0

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[1001.0, 1001.5]):
            with patch("ainews.fetcher.hf_papers.time.sleep") as mock_sleep:
                fetcher._rate_limit()

        # elapsed = 1.0 < 2.0, sleep(1.0)
        mock_sleep.assert_called_once()
        call_args = mock_sleep.call_args[0][0]
        assert abs(call_args - 1.0) < 0.01

    def test_rate_limit_no_sleep_when_enough_time_passed(
        self, fetcher: HFPapersFetcher
    ) -> None:
        """请求间隔超过 2s 时不需要 sleep."""
        fetcher._last_request_time = 1000.0

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[1003.0, 1003.0]):
            with patch("ainews.fetcher.hf_papers.time.sleep") as mock_sleep:
                fetcher._rate_limit()

        mock_sleep.assert_not_called()

    def test_rate_limit_updates_last_request_time(
        self, fetcher: HFPapersFetcher
    ) -> None:
        """rate_limit 更新 _last_request_time."""
        fetcher._last_request_time = 0.0

        with patch("ainews.fetcher.hf_papers.time.monotonic", return_value=500.0):
            with patch("ainews.fetcher.hf_papers.time.sleep"):
                fetcher._rate_limit()

        assert fetcher._last_request_time == 500.0


# ------------------------------------------------------------------
# 测试 test_connection
# ------------------------------------------------------------------


class TestConnection:
    def test_connection_ok(self, fetcher: HFPapersFetcher) -> None:
        """API 连通性正常."""
        resp = _make_response(status_code=200, json_data=[{"paper": {"id": "1"}}])
        fetcher._client.get.return_value = resp

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[0.0, 0.1]):
            result = fetcher.test_connection()

        assert result["ok"] is True
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0
        assert "1 篇" in result["detail"]

    def test_connection_http_error(self, fetcher: HFPapersFetcher) -> None:
        """API 返回非 200 状态码."""
        resp = _make_response(status_code=503)
        fetcher._client.get.return_value = resp

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[0.0, 0.05]):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "503" in result["error"]

    def test_connection_network_failure(self, fetcher: HFPapersFetcher) -> None:
        """网络异常."""
        fetcher._client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[0.0, 0.05]):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "Connection refused" in result["error"]

    def test_connection_timeout(self, fetcher: HFPapersFetcher) -> None:
        """请求超时."""
        fetcher._client.get.side_effect = httpx.TimeoutException("Read timed out")

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[0.0, 10.0]):
            result = fetcher.test_connection()

        assert result["ok"] is False
        assert "timed out" in result["error"]

    def test_connection_uses_today_date(self, fetcher: HFPapersFetcher) -> None:
        """test_connection 请求今天日期的论文."""
        resp = _make_response(status_code=200, json_data=[])
        fetcher._client.get.return_value = resp

        with patch("ainews.fetcher.hf_papers.time.monotonic", side_effect=[0.0, 0.01]):
            fetcher.test_connection()

        call_args = fetcher._client.get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params")
        # 确认 params 包含 date 参数
        assert params is not None
        assert "date" in params
