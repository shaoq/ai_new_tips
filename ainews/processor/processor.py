"""文章处理管线：读取文章、调用 LLM、解析结果、更新数据库."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from rich.console import Console  # NOTE: 进度输出依赖，项目已有 rich 依赖

from ainews.llm.client import LLMClient, LLMClientError, LLMResponseParseError, parse_json_response
from ainews.llm.prompts import MERGED_PROCESS_PROMPT
from ainews.processor.entity_handler import EntityHandler
from ainews.storage.models import Article

logger = logging.getLogger(__name__)
_console = Console()

# JSON 字段默认值
_DEFAULT_CATEGORY = ""
_DEFAULT_CATEGORY_CONFIDENCE = 0.0
_DEFAULT_SUMMARY_ZH = ""
_DEFAULT_RELEVANCE = 0
_DEFAULT_RELEVANCE_REASON = ""
_DEFAULT_TAGS: list[str] = []
_DEFAULT_ENTITIES: dict[str, list[str]] = {
    "people": [],
    "companies": [],
    "projects": [],
    "technologies": [],
}

# 每次调用间隔（秒）
CALL_INTERVAL = 0.5

# 每次运行默认处理上限（防止积压时单次运行时间过长）
DEFAULT_BATCH_LIMIT = 50


@dataclass(frozen=True)
class ProcessResult:
    """单篇文章处理结果."""

    article_id: int
    success: bool
    error: str = ""
    category: str = ""
    summary_zh: str = ""
    relevance: int = 0
    tags: list[str] = field(default_factory=list)


class ArticleProcessor:
    """文章处理器：调用 LLM 完成分类、摘要、评分、实体提取、标签生成."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def process_article(self, article: Article, session: Session) -> ProcessResult:
        """处理单篇文章：构建 Prompt、调用 LLM、解析 JSON、更新数据库.

        Args:
            article: 文章对象
            session: 数据库 session

        Returns:
            ProcessResult 处理结果
        """
        try:
            prompt = MERGED_PROCESS_PROMPT.format(
                title=article.title,
                source_name=article.source_name,
                content=article.content_raw[:3000],
            )
            raw_response = self._llm.call(prompt)
            parsed = parse_json_response(raw_response)
            self._apply_result(article, parsed, session)
            return ProcessResult(
                article_id=article.id,
                success=True,
                category=parsed.get("category", _DEFAULT_CATEGORY),
                summary_zh=parsed.get("summary_zh", _DEFAULT_SUMMARY_ZH),
                relevance=parsed.get("relevance", _DEFAULT_RELEVANCE),
                tags=parsed.get("tags", _DEFAULT_TAGS),
            )
        except (LLMClientError, LLMResponseParseError) as exc:
            logger.error("文章 %d 处理失败: %s", article.id, exc)
            return ProcessResult(
                article_id=article.id,
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.exception("文章 %d 处理异常: %s", article.id, exc)
            return ProcessResult(
                article_id=article.id,
                success=False,
                error=str(exc),
            )

    def process_unprocessed(self, session: Session, limit: int | None = None) -> list[ProcessResult]:
        """处理所有 processed=False 的文章.

        Args:
            session: 数据库 session
            limit: 限制处理数量。None 使用默认上限 50，0 表示不限制

        Returns:
            所有处理结果列表
        """
        batch_limit = DEFAULT_BATCH_LIMIT if limit is None else (limit if limit > 0 else None)

        statement = select(Article).where(Article.processed == False)  # noqa: E712
        if batch_limit is not None:
            statement = statement.limit(batch_limit)
        articles = session.exec(statement).all()

        if not articles:
            logger.info("没有需要处理的文章")
            return []

        logger.info("开始处理 %d 篇未处理文章", len(articles))
        results: list[ProcessResult] = []

        for i, article in enumerate(articles):
            result = self.process_article(article, session)
            results.append(result)
            session.commit()

            done = i + 1
            if done % 5 == 0 or done == len(articles):
                _console.print(
                    f"    [dim]·[/dim] Processed [cyan]{done}[/cyan]/[dim]{len(articles)}[/dim] articles"
                )

            if i < len(articles) - 1:
                time.sleep(CALL_INTERVAL)

        self._log_summary(results, "增量处理")
        return results

    def process_by_id(self, session: Session, article_id: int) -> ProcessResult | None:
        """按 ID 处理单篇文章（忽略 processed 状态）.

        Args:
            session: 数据库 session
            article_id: 文章 ID

        Returns:
            ProcessResult 或 None（文章不存在）
        """
        article = session.get(Article, article_id)
        if article is None:
            logger.error("文章 ID %d 不存在", article_id)
            return None

        result = self.process_article(article, session)
        session.commit()
        return result

    def process_all_force(self, session: Session) -> list[ProcessResult]:
        """强制重新处理所有文章.

        Args:
            session: 数据库 session

        Returns:
            所有处理结果列表
        """
        # 重置所有文章的 processed 状态
        statement = select(Article)
        articles = session.exec(statement).all()

        if not articles:
            logger.info("数据库中没有文章")
            return []

        for article in articles:
            article.processed = False
        session.commit()

        logger.info("开始强制处理全部 %d 篇文章", len(articles))
        results: list[ProcessResult] = []

        for i, article in enumerate(articles):
            result = self.process_article(article, session)
            results.append(result)
            session.commit()

            done = i + 1
            if done % 5 == 0 or done == len(articles):
                _console.print(
                    f"    [dim]·[/dim] Processed [cyan]{done}[/cyan]/[dim]{len(articles)}[/dim] articles"
                )

            if i < len(articles) - 1:
                time.sleep(CALL_INTERVAL)

        self._log_summary(results, "强制全量处理")
        return results

    def _apply_result(
        self, article: Article, parsed: dict[str, Any], session: Session
    ) -> None:
        """将 LLM 解析结果应用到文章对象并处理实体.

        Args:
            article: 文章对象
            parsed: LLM 返回的解析后 JSON
            session: 数据库 session
        """
        category = parsed.get("category", _DEFAULT_CATEGORY)
        if not category:
            logger.warning("文章 %d 缺少 category 字段", article.id)

        relevance = parsed.get("relevance", _DEFAULT_RELEVANCE)
        try:
            relevance = int(relevance)
        except (ValueError, TypeError):
            logger.warning("文章 %d relevance 值无效: %s", article.id, relevance)
            relevance = 0

        tags = parsed.get("tags", _DEFAULT_TAGS)
        if not isinstance(tags, list):
            logger.warning("文章 %d tags 不是列表: %s", article.id, type(tags).__name__)
            tags = _DEFAULT_TAGS

        entities = parsed.get("entities", _DEFAULT_ENTITIES)
        if not isinstance(entities, dict):
            logger.warning("文章 %d entities 不是字典: %s", article.id, type(entities).__name__)
            entities = _DEFAULT_ENTITIES

        article.category = category
        article.summary_zh = parsed.get("summary_zh", _DEFAULT_SUMMARY_ZH)
        article.relevance = relevance
        article.tags = json.dumps(tags, ensure_ascii=False)
        article.processed = True

        # 实体入库
        if article.id is not None and entities:
            handler = EntityHandler(session)
            handler.upsert_entities(article.id, entities)

        session.add(article)

    def _log_summary(self, results: list[ProcessResult], mode: str) -> None:
        """输出处理结果摘要日志."""
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        logger.info(
            "%s完成: 成功 %d 篇, 失败 %d 篇",
            mode,
            success_count,
            fail_count,
        )
        if fail_count > 0:
            failed_ids = [r.article_id for r in results if not r.success]
            logger.warning("失败文章 ID: %s", failed_ids)
