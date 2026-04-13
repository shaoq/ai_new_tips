"""文章处理器测试."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ainews.llm.client import LLMClient, LLMClientError, LLMResponseParseError
from ainews.processor.processor import ArticleProcessor, ProcessResult
from ainews.storage.models import Article


@pytest.fixture
def engine():
    """创建内存数据库引擎."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """创建数据库 session."""
    from sqlmodel import Session
    with Session(engine) as s:
        yield s


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """创建 mock LLM 客户端."""
    client = MagicMock(spec=LLMClient)
    return client


@pytest.fixture
def processor(mock_llm_client: MagicMock) -> ArticleProcessor:
    """创建 ArticleProcessor."""
    return ArticleProcessor(mock_llm_client)


def _make_article(**overrides: object) -> Article:
    defaults = {
        "url": "https://example.com/test",
        "url_hash": "abc123",
        "title": "Test Article Title",
        "content_raw": "This is the article content about AI and GPT.",
        "source": "test",
        "source_name": "TestSource",
        "processed": False,
    }
    defaults.update(overrides)
    return Article(**defaults)  # type: ignore[arg-type]


VALID_LLM_RESPONSE = json.dumps({
    "category": "industry",
    "category_confidence": 0.95,
    "summary_zh": "这是一篇关于AI的测试文章。",
    "relevance": 9,
    "relevance_reason": "直接讨论AI技术进展",
    "tags": ["ai", "gpt", "llm"],
    "entities": {
        "people": ["Sam Altman"],
        "companies": ["OpenAI"],
        "projects": ["GPT-5"],
        "technologies": ["llm"],
    },
})


class TestProcessArticle:
    """单篇文章处理测试."""

    def test_process_article_success(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_article(article, session)

        assert result.success is True
        assert result.article_id == article.id
        assert result.category == "industry"
        assert result.relevance == 9
        assert result.tags == ["ai", "gpt", "llm"]
        assert article.processed is True
        assert article.category == "industry"
        assert article.summary_zh == "这是一篇关于AI的测试文章。"
        assert article.relevance == 9

    def test_process_article_llm_error(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.side_effect = LLMClientError("API error")

        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_article(article, session)

        assert result.success is False
        assert "API error" in result.error
        assert result.article_id == article.id

    def test_process_article_json_parse_error(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = "not valid json"

        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        # The raw response is not valid JSON, but parse_json_response is called
        # inside process_article. Since the raw string is not JSON and not in a code block,
        # it will raise LLMResponseParseError which is caught.
        result = processor.process_article(article, session)

        assert result.success is False

    def test_process_article_with_markdown_json(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        wrapped_response = f"```json\n{VALID_LLM_RESPONSE}\n```"
        mock_llm_client.call.return_value = wrapped_response

        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_article(article, session)

        assert result.success is True
        assert result.category == "industry"

    def test_process_article_partial_fields(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        partial_response = json.dumps({
            "category": "research",
            "summary_zh": "Partial content",
            "relevance": 5,
            "tags": ["ml"],
            "entities": {
                "people": [],
                "companies": [],
                "projects": [],
                "technologies": [],
            },
        })
        mock_llm_client.call.return_value = partial_response

        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_article(article, session)

        assert result.success is True
        assert result.category == "research"

    def test_process_article_truncates_long_content(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        long_content = "x" * 10000
        article = _make_article(content_raw=long_content)
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_article(article, session)
        assert result.success is True

        # Verify content was truncated in the prompt call
        call_args = mock_llm_client.call.call_args[0][0]
        assert "x" * 3000 in call_args
        assert "x" * 3001 not in call_args


class TestProcessUnprocessed:
    """批量处理未处理文章测试."""

    @patch("ainews.processor.processor.time.sleep")
    def test_process_unprocessed_articles(
        self, mock_sleep: MagicMock, processor: ArticleProcessor,
        mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        articles = [
            _make_article(title=f"Article {i}", url=f"https://example.com/test{i}")
            for i in range(3)
        ]
        for a in articles:
            session.add(a)
        session.commit()

        results = processor.process_unprocessed(session)

        assert len(results) == 3
        assert all(r.success for r in results)

    @patch("ainews.processor.processor.time.sleep")
    def test_process_unprocessed_no_articles(
        self, mock_sleep: MagicMock, processor: ArticleProcessor,
        mock_llm_client: MagicMock, session: Session
    ) -> None:
        results = processor.process_unprocessed(session)

        assert results == []
        mock_llm_client.call.assert_not_called()

    @patch("ainews.processor.processor.time.sleep")
    def test_process_unprocessed_single_failure_continues(
        self, mock_sleep: MagicMock, processor: ArticleProcessor,
        mock_llm_client: MagicMock, session: Session
    ) -> None:
        call_count = 0

        def side_effect(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise LLMClientError("API error on article 2")
            return VALID_LLM_RESPONSE

        mock_llm_client.call.side_effect = side_effect

        articles = [
            _make_article(title=f"Article {i}", url=f"https://example.com/test{i}")
            for i in range(3)
        ]
        for a in articles:
            session.add(a)
        session.commit()

        results = processor.process_unprocessed(session)

        assert len(results) == 3
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 2
        assert len(failures) == 1

    @patch("ainews.processor.processor.time.sleep")
    def test_process_unprocessed_skips_processed(
        self, mock_sleep: MagicMock, processor: ArticleProcessor,
        mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        unprocessed = _make_article(title="Unprocessed")
        processed = _make_article(title="Processed", url="https://example.com/p", processed=True)
        session.add(unprocessed)
        session.add(processed)
        session.commit()

        results = processor.process_unprocessed(session)

        assert len(results) == 1
        assert results[0].success is True


class TestProcessById:
    """按 ID 处理文章测试."""

    def test_process_by_id_success(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        article = _make_article()
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_by_id(session, article.id)

        assert result is not None
        assert result.success is True
        assert result.article_id == article.id

    def test_process_by_id_not_found(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        result = processor.process_by_id(session, 999)

        assert result is None

    def test_process_by_id_ignores_processed_status(
        self, processor: ArticleProcessor, mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        article = _make_article(processed=True)
        session.add(article)
        session.commit()
        session.refresh(article)

        result = processor.process_by_id(session, article.id)

        assert result is not None
        assert result.success is True


class TestProcessAllForce:
    """强制全量处理测试."""

    @patch("ainews.processor.processor.time.sleep")
    def test_process_all_force_processes_everything(
        self, mock_sleep: MagicMock, processor: ArticleProcessor,
        mock_llm_client: MagicMock, session: Session
    ) -> None:
        mock_llm_client.call.return_value = VALID_LLM_RESPONSE

        articles = [
            _make_article(title="Unprocessed"),
            _make_article(title="Processed", url="https://example.com/p", processed=True),
        ]
        for a in articles:
            session.add(a)
        session.commit()

        results = processor.process_all_force(session)

        assert len(results) == 2
        assert all(r.success for r in results)

    @patch("ainews.processor.processor.time.sleep")
    def test_process_all_force_empty_db(
        self, mock_sleep: MagicMock, processor: ArticleProcessor,
        mock_llm_client: MagicMock, session: Session
    ) -> None:
        results = processor.process_all_force(session)

        assert results == []
        mock_llm_client.call.assert_not_called()
