"""流水线编排引擎."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from rich.console import Console
from rich.table import Table


class StepStatus(str, Enum):
    OK = "OK"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass
class StepResult:
    """单个步骤执行结果."""

    name: str
    status: StepStatus
    duration: float = 0.0
    count: int = 0
    error: str = ""


@dataclass
class PipelineStep:
    """流水线步骤定义."""

    name: str
    execute_fn: Callable[..., Any]
    skippable: bool = False
    dry_run_desc: str = ""


@dataclass
class RunOptions:
    """流水线运行选项."""

    backfill: str = ""
    source: str = ""
    skip_sync: bool = False
    skip_push: bool = False
    trending_only_push: bool = False
    dry_run: bool = False
    verbose: bool = False
    limit: int = 0


@dataclass
class PipelineResult:
    """流水线执行结果."""

    steps: list[StepResult] = field(default_factory=list)
    total_duration: float = 0.0

    @property
    def all_ok(self) -> bool:
        return all(s.status != StepStatus.FAILED for s in self.steps)

    @property
    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)


class PipelineRunner:
    """流水线执行器."""

    def __init__(self, steps: list[PipelineStep], options: RunOptions) -> None:
        self.steps = steps
        self.options = options
        self.console = Console()

    def run(self) -> PipelineResult:
        """按序执行所有步骤."""
        result = PipelineResult()
        start = time.time()

        for step in self.steps:
            # 检查是否应该跳过
            if self._should_skip(step):
                result.steps.append(StepResult(name=step.name, status=StepStatus.SKIPPED))
                self._print_step(step.name, StepStatus.SKIPPED)
                continue

            # dry-run 模式
            if self.options.dry_run:
                desc = step.dry_run_desc or f"Will execute: {step.name}"
                result.steps.append(StepResult(name=step.name, status=StepStatus.SKIPPED))
                self.console.print(f"  [dim]DRY-RUN[/dim] {step.name}: {desc}")
                continue

            # 实际执行
            self.console.print(f"  [dim]▸[/dim] {step.name}...")
            step_start = time.time()
            try:
                count = step.execute_fn(self.options)
                duration = time.time() - step_start
                result.steps.append(
                    StepResult(name=step.name, status=StepStatus.OK, duration=duration, count=count or 0)
                )
                self._print_step(step.name, StepStatus.OK, duration, count)
            except Exception as e:
                duration = time.time() - step_start
                result.steps.append(
                    StepResult(name=step.name, status=StepStatus.FAILED, duration=duration, error=str(e))
                )
                self._print_step(step.name, StepStatus.FAILED, duration, error=str(e))

        result.total_duration = time.time() - start
        return result

    def _should_skip(self, step: PipelineStep) -> bool:
        if self.options.skip_sync and "sync" in step.name.lower():
            return True
        if self.options.skip_push and "push" in step.name.lower():
            return True
        return False

    def _print_step(
        self,
        name: str,
        status: StepStatus,
        duration: float = 0.0,
        count: int = 0,
        error: str = "",
    ) -> None:
        color = {
            StepStatus.OK: "green",
            StepStatus.SKIPPED: "yellow",
            StepStatus.FAILED: "red",
        }[status]
        msg = f"  [{color}]{status.value:>8}[/{color}] {name}"
        if duration > 0:
            msg += f" ({duration:.1f}s"
            if count > 0:
                msg += f", {count} items"
            msg += ")"
        if error:
            msg += f" — {error}"
        self.console.print(msg)

    def print_summary(self, result: PipelineResult) -> None:
        """输出执行摘要."""
        table = Table(title="Pipeline Summary")
        table.add_column("Step", style="cyan")
        table.add_column("Status")
        table.add_column("Items")
        table.add_column("Time")

        for step in result.steps:
            color = {
                StepStatus.OK: "green",
                StepStatus.SKIPPED: "yellow",
                StepStatus.FAILED: "red",
            }[step.status]
            table.add_row(
                step.name,
                f"[{color}]{step.status.value}[/{color}]",
                str(step.count) if step.count else "-",
                f"{step.duration:.1f}s" if step.duration > 0 else "-",
            )

        table.add_row("─" * 20, "─" * 10, "─" * 6, "─" * 6)
        table.add_row("Total", "", "", f"{result.total_duration:.1f}s")
        self.console.print(table)
