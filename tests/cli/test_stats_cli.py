"""测试 CLI stats 子命令集."""

from __future__ import annotations

from typer.testing import CliRunner

from ainews.cli.main import app

runner = CliRunner()


class TestStatsToday:
    """ainews stats today 测试."""

    def test_today_command(self) -> None:
        result = runner.invoke(app, ["stats", "today"])
        assert result.exit_code == 0


class TestStatsWeekly:
    """ainews stats weekly 测试."""

    def test_weekly_command(self) -> None:
        result = runner.invoke(app, ["stats", "weekly"])
        assert result.exit_code == 0


class TestStatsTrending:
    """ainews stats trending 测试."""

    def test_trending_default(self) -> None:
        result = runner.invoke(app, ["stats", "trending"])
        assert result.exit_code == 0

    def test_trending_with_options(self) -> None:
        result = runner.invoke(app, ["stats", "trending", "--days", "7", "--limit", "10"])
        assert result.exit_code == 0


class TestStatsBySource:
    """ainews stats by-source 测试."""

    def test_by_source(self) -> None:
        result = runner.invoke(app, ["stats", "by-source"])
        assert result.exit_code == 0


class TestStatsByCategory:
    """ainews stats by-category 测试."""

    def test_by_category(self) -> None:
        result = runner.invoke(app, ["stats", "by-category"])
        assert result.exit_code == 0


class TestStatsNewEntities:
    """ainews stats new-entities 测试."""

    def test_new_entities(self) -> None:
        result = runner.invoke(app, ["stats", "new-entities"])
        assert result.exit_code == 0

    def test_new_entities_with_type(self) -> None:
        result = runner.invoke(app, ["stats", "new-entities", "--type", "person"])
        assert result.exit_code == 0


class TestStatsTopPeople:
    """ainews stats top-people 测试."""

    def test_top_people(self) -> None:
        result = runner.invoke(app, ["stats", "top-people"])
        assert result.exit_code == 0

    def test_top_people_with_limit(self) -> None:
        result = runner.invoke(app, ["stats", "top-people", "--limit", "5"])
        assert result.exit_code == 0
