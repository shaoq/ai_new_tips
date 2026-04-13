"""测试 plist 模板生成."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from ainews.scheduler.templates import ScheduleConfig, generate_plist, get_schedules


class TestScheduleConfig:
    """ScheduleConfig 测试."""

    def test_plist_filename(self) -> None:
        config = ScheduleConfig(
            name="morning", label="com.ainews.morning",
            command_args=["/usr/local/bin/ainews", "run"],
            hour=8, minute=0,
        )
        assert config.plist_filename == "com.ainews.morning.plist"

    def test_plist_path(self) -> None:
        config = ScheduleConfig(
            name="morning", label="com.ainews.morning",
            command_args=["/usr/local/bin/ainews", "run"],
            hour=8, minute=0,
        )
        assert "LaunchAgents" in str(config.plist_path)
        assert config.plist_path.name == "com.ainews.morning.plist"


class TestGeneratePlist:
    """plist XML 生成测试."""

    def test_basic_structure(self) -> None:
        config = ScheduleConfig(
            name="morning", label="com.ainews.morning",
            command_args=["/usr/local/bin/ainews", "run"],
            hour=8, minute=0,
            log_path="/tmp/ainews-morning.log",
            err_path="/tmp/ainews-morning.err",
        )
        xml = generate_plist(config)
        root = ET.fromstring(xml)

        # 找到 dict 下的所有 key-value 对
        dict_elem = root.find("dict")
        keys = [el.text for el in dict_elem.findall("key")]

        assert "Label" in keys
        assert "ProgramArguments" in keys
        assert "StartCalendarInterval" in keys
        assert "StandardOutPath" in keys
        assert "StandardErrorPath" in keys
        assert "EnvironmentVariables" in keys

    def test_morning_schedule(self) -> None:
        config = ScheduleConfig(
            name="morning", label="com.ainews.morning",
            command_args=["/usr/local/bin/ainews", "run"],
            hour=8, minute=0,
        )
        xml = generate_plist(config)
        assert "com.ainews.morning" in xml
        assert "ainews" in xml
        assert "run" in xml

    def test_weekly_with_weekday(self) -> None:
        config = ScheduleConfig(
            name="weekly", label="com.ainews.weekly",
            command_args=["/usr/local/bin/ainews", "push", "dingtalk", "--weekly"],
            hour=20, minute=30, weekday=0,
        )
        xml = generate_plist(config)
        assert "Weekday" in xml
        assert "0" in xml  # weekday=0 (Sunday)

    def test_daily_no_weekday(self) -> None:
        config = ScheduleConfig(
            name="noon", label="com.ainews.noon",
            command_args=["/usr/local/bin/ainews", "run"],
            hour=12, minute=30,
        )
        xml = generate_plist(config)
        root = ET.fromstring(xml)
        dict_elem = root.find("dict")

        keys = [el.text for el in dict_elem.findall("key")]
        idx = keys.index("StartCalendarInterval")
        interval = list(dict_elem)[idx + 1]
        interval_keys = [el.text for el in interval.findall("key")]
        assert "Weekday" not in interval_keys

    def test_noon_trending_flag(self) -> None:
        schedules = get_schedules("/usr/local/bin/ainews")
        noon = [s for s in schedules if s.name == "noon"][0]
        assert "--trending-only-push" in noon.command_args


class TestGetSchedules:
    """get_schedules 测试."""

    def test_returns_four_schedules(self) -> None:
        schedules = get_schedules("/usr/local/bin/ainews")
        assert len(schedules) == 4

    def test_schedule_names(self) -> None:
        schedules = get_schedules("/usr/local/bin/ainews")
        names = [s.name for s in schedules]
        assert "morning" in names
        assert "noon" in names
        assert "evening" in names
        assert "weekly" in names

    def test_weekly_runs_push(self) -> None:
        schedules = get_schedules("/usr/local/bin/ainews")
        weekly = [s for s in schedules if s.name == "weekly"][0]
        assert "push" in weekly.command_args
        assert "--weekly" in weekly.command_args
