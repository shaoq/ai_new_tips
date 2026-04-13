"""Prompt 模板测试."""

from __future__ import annotations

from ainews.llm.prompts import MERGED_PROCESS_PROMPT


class TestMergedProcessPrompt:
    """MERGED_PROCESS_PROMPT 模板测试."""

    def test_template_has_required_placeholders(self) -> None:
        assert "{title}" in MERGED_PROCESS_PROMPT
        assert "{source_name}" in MERGED_PROCESS_PROMPT
        assert "{content}" in MERGED_PROCESS_PROMPT

    def test_template_renders_correctly(self) -> None:
        rendered = MERGED_PROCESS_PROMPT.format(
            title="GPT-6 发布",
            source_name="HackerNews",
            content="OpenAI announces GPT-6...",
        )
        assert "GPT-6 发布" in rendered
        assert "HackerNews" in rendered
        assert "OpenAI announces GPT-6..." in rendered

    def test_template_contains_json_schema_requirements(self) -> None:
        assert "category" in MERGED_PROCESS_PROMPT
        assert "industry" in MERGED_PROCESS_PROMPT
        assert "research" in MERGED_PROCESS_PROMPT
        assert "tools" in MERGED_PROCESS_PROMPT
        assert "safety" in MERGED_PROCESS_PROMPT
        assert "policy" in MERGED_PROCESS_PROMPT
        assert "category_confidence" in MERGED_PROCESS_PROMPT
        assert "summary_zh" in MERGED_PROCESS_PROMPT
        assert "relevance" in MERGED_PROCESS_PROMPT
        assert "relevance_reason" in MERGED_PROCESS_PROMPT
        assert "tags" in MERGED_PROCESS_PROMPT
        assert "entities" in MERGED_PROCESS_PROMPT
        assert "people" in MERGED_PROCESS_PROMPT
        assert "companies" in MERGED_PROCESS_PROMPT
        assert "projects" in MERGED_PROCESS_PROMPT
        assert "technologies" in MERGED_PROCESS_PROMPT

    def test_template_requests_json_only(self) -> None:
        assert "JSON" in MERGED_PROCESS_PROMPT
        assert "只返回 JSON" in MERGED_PROCESS_PROMPT

    def test_template_specifies_relevance_range(self) -> None:
        assert "1" in MERGED_PROCESS_PROMPT
        assert "10" in MERGED_PROCESS_PROMPT

    def test_template_specifies_tags_format(self) -> None:
        assert "英文小写" in MERGED_PROCESS_PROMPT
        assert "连字符" in MERGED_PROCESS_PROMPT

    def test_template_no_unfilled_placeholders_after_render(self) -> None:
        rendered = MERGED_PROCESS_PROMPT.format(
            title="Test",
            source_name="TestSource",
            content="Test content",
        )
        assert "{title}" not in rendered
        assert "{source_name}" not in rendered
        assert "{content}" not in rendered
