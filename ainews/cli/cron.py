"""CLI cron 命令 — macOS launchd 定时任务管理."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ainews.scheduler.templates import get_schedules, generate_plist
from ainews.scheduler.launchd import (
    launchctl_load,
    launchctl_unload,
    launchctl_kickstart,
    launchctl_list,
    write_plist,
    delete_plist,
    get_ainews_plist_files,
)

cron_app = typer.Typer(help="定时任务管理 (macOS launchd)", no_args_is_help=True)
console = Console()


@cron_app.command("install")
def cron_install() -> None:
    """安装四组定时任务."""
    try:
        schedules = get_schedules()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    for sched in schedules:
        plist_content = generate_plist(sched)
        if sched.plist_path.exists():
            console.print(f"[yellow]{sched.name}[/yellow]: plist 已存在，覆盖...")
            ok, err = launchctl_unload(sched.plist_path)
            if not ok and err:
                console.print(f"  [dim]unload warning: {err}[/dim]")

        write_plist(sched.plist_path, plist_content)
        ok, err = launchctl_load(sched.plist_path)
        if ok:
            console.print(f"[green]{sched.name}[/green]: installed ({sched.hour:02d}:{sched.minute:02d})")
        else:
            console.print(f"[red]{sched.name}[/red]: load failed — {err}")

    console.print("\n[green]Done.[/green] Run [bold]ainews cron list[/bold] to verify.")


@cron_app.command("uninstall")
def cron_uninstall(
    name: str = typer.Option("", "--name", help="卸载单个任务（morning/noon/evening/weekly）"),
) -> None:
    """卸载定时任务."""
    schedules = get_schedules("ainews")  # 不需要真实路径，仅获取配置
    if name:
        schedules = [s for s in schedules if s.name == name]
        if not schedules:
            console.print(f"[yellow]任务 '{name}' 不存在[/yellow]")
            return

    for sched in schedules:
        if not sched.plist_path.exists():
            console.print(f"[yellow]{sched.name}[/yellow]: plist 不存在，跳过")
            continue
        ok, err = launchctl_unload(sched.plist_path)
        delete_plist(sched.plist_path)
        if ok or "No such process" in (err or ""):
            console.print(f"[green]{sched.name}[/green]: uninstalled")
        else:
            console.print(f"[yellow]{sched.name}[/yellow]: unloaded with warning — {err}")

    console.print("[green]Done.[/green]")


@cron_app.command("list")
def cron_list() -> None:
    """查看定时任务状态."""
    plist_files = get_ainews_plist_files()
    if not plist_files:
        console.print("[yellow]未安装任何定时任务[/yellow]")
        console.print("运行 [bold]ainews cron install[/bold] 安装")
        return

    statuses = launchctl_list()

    table = Table(title="Ainews Cron Jobs")
    table.add_column("Name", style="cyan")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("PID")
    table.add_column("Exit")

    schedules = get_schedules("ainews")
    name_map = {s.label: s for s in schedules}

    for pf in plist_files:
        label = pf.stem  # com.ainews.morning
        sched = name_map.get(label)
        name = sched.name if sched else label.replace("com.ainews.", "")
        schedule = f"{sched.hour:02d}:{sched.minute:02d}" if sched else "?"

        status = statuses.get(label)
        if status and status.loaded:
            status_str = "[green]loaded[/green]"
            pid = str(status.pid) if status.pid else "-"
            exit_code = str(status.last_exit) if status.last_exit is not None else "-"
        else:
            status_str = "[yellow]not loaded[/yellow]"
            pid = "-"
            exit_code = "-"

        table.add_row(name, schedule, status_str, pid, exit_code)

    console.print(table)


@cron_app.command("pause")
def cron_pause() -> None:
    """暂停所有定时任务（保留 plist）."""
    plist_files = get_ainews_plist_files()
    statuses = launchctl_list()

    if not plist_files:
        console.print("[yellow]未安装任何定时任务[/yellow]")
        return

    paused = 0
    for pf in plist_files:
        label = pf.stem
        status = statuses.get(label)
        if status and status.loaded:
            ok, _ = launchctl_unload(pf)
            name = label.replace("com.ainews.", "")
            if ok:
                console.print(f"[green]{name}[/green]: paused")
                paused += 1
        else:
            name = label.replace("com.ainews.", "")
            console.print(f"[dim]{name}: already not loaded[/dim]")

    if paused == 0:
        console.print("[yellow]所有任务已处于暂停状态[/yellow]")


@cron_app.command("resume")
def cron_resume() -> None:
    """恢复所有已暂停的定时任务."""
    plist_files = get_ainews_plist_files()
    statuses = launchctl_list()

    if not plist_files:
        console.print("[yellow]未安装任何定时任务[/yellow]")
        return

    resumed = 0
    for pf in plist_files:
        label = pf.stem
        status = statuses.get(label)
        if not status or not status.loaded:
            ok, err = launchctl_load(pf)
            name = label.replace("com.ainews.", "")
            if ok:
                console.print(f"[green]{name}[/green]: resumed")
                resumed += 1
            else:
                console.print(f"[red]{name}[/red]: {err}")
        else:
            name = label.replace("com.ainews.", "")
            console.print(f"[dim]{name}: already running[/dim]")

    if resumed == 0:
        console.print("[yellow]所有任务已处于运行状态[/yellow]")


@cron_app.command("trigger")
def cron_trigger(
    name: str = typer.Option(..., "--name", help="任务名称 (morning/noon/evening/weekly)"),
) -> None:
    """手动触发指定定时任务."""
    label = f"com.ainews.{name}"
    statuses = launchctl_list()
    status = statuses.get(label)

    if not status or not status.loaded:
        console.print(f"[red]任务 '{name}' 未加载[/red]")
        console.print("运行 [bold]ainews cron install[/bold] 或 [bold]ainews cron resume[/bold]")
        raise typer.Exit(1)

    ok, err = launchctl_kickstart(label)
    if ok:
        console.print(f"[green]{name}[/green]: triggered")
    else:
        console.print(f"[red]{name}[/red]: trigger failed — {err}")
        raise typer.Exit(1)
