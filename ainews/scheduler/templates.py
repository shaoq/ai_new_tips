"""定时任务配置与 plist 模板生成."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString


@dataclass
class ScheduleConfig:
    """定时任务配置."""

    name: str
    label: str
    command_args: list[str]
    hour: int
    minute: int
    weekday: int | None = None  # 0=Sunday, None=daily
    log_path: str = ""
    err_path: str = ""

    @property
    def plist_filename(self) -> str:
        return f"com.ainews.{self.name}.plist"

    @property
    def plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / self.plist_filename


def get_ainews_path() -> str:
    """解析 ainews 可执行文件的绝对路径."""
    path = shutil.which("ainews")
    if path is None:
        msg = "无法找到 ainews 可执行文件，请确认已安装 (uv tool install . 或 pip install -e .)"
        raise FileNotFoundError(msg)
    return path


def get_schedules(ainews_path: str | None = None) -> list[ScheduleConfig]:
    """获取四组定时任务配置."""
    if ainews_path is None:
        ainews_path = get_ainews_path()

    return [
        ScheduleConfig(
            name="morning",
            label="com.ainews.morning",
            command_args=[ainews_path, "run"],
            hour=8,
            minute=0,
            log_path="/tmp/ainews-morning.log",
            err_path="/tmp/ainews-morning.err",
        ),
        ScheduleConfig(
            name="noon",
            label="com.ainews.noon",
            command_args=[ainews_path, "run", "--trending-only-push"],
            hour=12,
            minute=30,
            log_path="/tmp/ainews-noon.log",
            err_path="/tmp/ainews-noon.err",
        ),
        ScheduleConfig(
            name="evening",
            label="com.ainews.evening",
            command_args=[ainews_path, "run"],
            hour=20,
            minute=0,
            log_path="/tmp/ainews-evening.log",
            err_path="/tmp/ainews-evening.err",
        ),
        ScheduleConfig(
            name="weekly",
            label="com.ainews.weekly",
            command_args=[ainews_path, "push", "dingtalk", "--weekly"],
            hour=20,
            minute=30,
            weekday=0,
            log_path="/tmp/ainews-weekly.log",
            err_path="/tmp/ainews-weekly.err",
        ),
    ]


def generate_plist(config: ScheduleConfig) -> str:
    """生成 launchd plist XML 字符串."""
    import os

    plist = Element("plist", version="1.0")
    dict_elem = SubElement(plist, "dict")

    def _add(key: str, value: str | int) -> None:
        SubElement(dict_elem, "key").text = key
        if isinstance(value, int):
            SubElement(dict_elem, "integer").text = str(value)
        else:
            SubElement(dict_elem, "string").text = value

    _add("Label", config.label)

    # ProgramArguments
    SubElement(dict_elem, "key").text = "ProgramArguments"
    array = SubElement(dict_elem, "array")
    for arg in config.command_args:
        SubElement(array, "string").text = arg

    # StartCalendarInterval
    SubElement(dict_elem, "key").text = "StartCalendarInterval"
    interval = SubElement(dict_elem, "dict")
    SubElement(interval, "key").text = "Hour"
    SubElement(interval, "integer").text = str(config.hour)
    SubElement(interval, "key").text = "Minute"
    SubElement(interval, "integer").text = str(config.minute)
    if config.weekday is not None:
        SubElement(interval, "key").text = "Weekday"
        SubElement(interval, "integer").text = str(config.weekday)

    _add("StandardOutPath", config.log_path)
    _add("StandardErrorPath", config.err_path)

    # EnvironmentVariables
    SubElement(dict_elem, "key").text = "EnvironmentVariables"
    env_dict = SubElement(dict_elem, "dict")
    SubElement(env_dict, "key").text = "PATH"
    SubElement(env_dict, "string").text = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")

    raw = tostring(plist, encoding="unicode", xml_declaration=True)
    # Pretty print
    dom = parseString(raw)
    return dom.toprettyxml(indent="\t")
