"""CLI 主命令入口."""

from __future__ import annotations

from typing import Optional

import typer

from ainews import __version__

app = typer.Typer(
    name="ainews",
    help="AI News Tips - AI 新闻采集、处理与推送工具",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ainews {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", help="显示版本号", callback=_version_callback, is_eager=True
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用详细日志 (DEBUG)"),
) -> None:
    """AI News Tips - AI 新闻采集、处理与推送工具."""
    if verbose:
        from ainews.utils.logging import set_log_level
        set_log_level("DEBUG")


# 注册子命令组（延迟导入避免循环依赖）
from ainews.cli.config import config_app  # noqa: E402
from ainews.cli.db import db_app  # noqa: E402
from ainews.cli.doctor import doctor_command  # noqa: E402
from ainews.cli.push import push_app  # noqa: E402
from ainews.cli.fetch import fetch_app, fetch_command  # noqa: E402
from ainews.cli.sources import sources_app  # noqa: E402
from ainews.cli.process import app as process_app  # noqa: E402

app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")
app.add_typer(push_app, name="push")
app.command(name="doctor")(doctor_command)
app.add_typer(fetch_app, name="fetch")
app.command(name="fetch", deprecated=True)(fetch_command)
app.add_typer(sources_app, name="sources")
app.add_typer(process_app, name="process")
