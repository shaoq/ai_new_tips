"""测试 PipelineRunner."""

from __future__ import annotations

import pytest

from ainews.pipeline.runner import (
    PipelineRunner,
    PipelineResult,
    PipelineStep,
    RunOptions,
    StepResult,
    StepStatus,
)


def _ok_step(options: RunOptions) -> int:
    return 10


def _fail_step(options: RunOptions) -> int:
    msg = "something went wrong"
    raise RuntimeError(msg)


def _count_step(options: RunOptions) -> int:
    return 5


class TestPipelineStep:
    """PipelineStep 数据类测试."""

    def test_create_step(self) -> None:
        step = PipelineStep(name="Test", execute_fn=_ok_step)
        assert step.name == "Test"
        assert step.skippable is False

    def test_step_with_dry_run_desc(self) -> None:
        step = PipelineStep(name="Fetch", execute_fn=_ok_step, dry_run_desc="Will fetch")
        assert step.dry_run_desc == "Will fetch"


class TestPipelineResult:
    """PipelineResult 测试."""

    def test_all_ok(self) -> None:
        result = PipelineResult(steps=[
            StepResult(name="A", status=StepStatus.OK),
            StepResult(name="B", status=StepStatus.OK),
        ])
        assert result.all_ok is True
        assert result.has_failures is False

    def test_has_failure(self) -> None:
        result = PipelineResult(steps=[
            StepResult(name="A", status=StepStatus.OK),
            StepResult(name="B", status=StepStatus.FAILED),
        ])
        assert result.all_ok is False
        assert result.has_failures is True

    def test_empty_result(self) -> None:
        result = PipelineResult()
        assert result.all_ok is True
        assert result.has_failures is False


class TestPipelineRunner:
    """PipelineRunner 测试."""

    def test_normal_execution(self) -> None:
        steps = [
            PipelineStep(name="Step1", execute_fn=_ok_step),
            PipelineStep(name="Step2", execute_fn=_count_step),
        ]
        runner = PipelineRunner(steps, RunOptions())
        result = runner.run()

        assert len(result.steps) == 2
        assert result.steps[0].status == StepStatus.OK
        assert result.steps[0].count == 10
        assert result.steps[1].status == StepStatus.OK
        assert result.steps[1].count == 5
        assert result.total_duration > 0

    def test_error_isolation(self) -> None:
        steps = [
            PipelineStep(name="OK", execute_fn=_ok_step),
            PipelineStep(name="Fail", execute_fn=_fail_step),
            PipelineStep(name="After", execute_fn=_count_step),
        ]
        runner = PipelineRunner(steps, RunOptions())
        result = runner.run()

        assert result.steps[0].status == StepStatus.OK
        assert result.steps[1].status == StepStatus.FAILED
        assert "something went wrong" in result.steps[1].error
        assert result.steps[2].status == StepStatus.OK  # continues after failure

    def test_skip_sync(self) -> None:
        steps = [
            PipelineStep(name="Sync Obsidian", execute_fn=_ok_step, skippable=True),
            PipelineStep(name="Push DingTalk", execute_fn=_ok_step, skippable=True),
        ]
        runner = PipelineRunner(steps, RunOptions(skip_sync=True))
        result = runner.run()

        assert result.steps[0].status == StepStatus.SKIPPED
        assert result.steps[1].status == StepStatus.OK

    def test_skip_push(self) -> None:
        steps = [
            PipelineStep(name="Sync", execute_fn=_ok_step, skippable=True),
            PipelineStep(name="Push DingTalk", execute_fn=_ok_step, skippable=True),
        ]
        runner = PipelineRunner(steps, RunOptions(skip_push=True))
        result = runner.run()

        assert result.steps[0].status == StepStatus.OK
        assert result.steps[1].status == StepStatus.SKIPPED

    def test_dry_run(self) -> None:
        steps = [
            PipelineStep(name="Step1", execute_fn=_ok_step, dry_run_desc="Will do X"),
            PipelineStep(name="Step2", execute_fn=_fail_step),
        ]
        runner = PipelineRunner(steps, RunOptions(dry_run=True))
        result = runner.run()

        # dry-run should not call execute_fn, so no failure
        assert all(s.status == StepStatus.SKIPPED for s in result.steps)

    def test_all_steps_fail(self) -> None:
        steps = [
            PipelineStep(name="A", execute_fn=_fail_step),
            PipelineStep(name="B", execute_fn=_fail_step),
        ]
        runner = PipelineRunner(steps, RunOptions())
        result = runner.run()

        assert result.has_failures is True
        assert all(s.status == StepStatus.FAILED for s in result.steps)

    def test_print_summary(self) -> None:
        steps = [PipelineStep(name="Test", execute_fn=_ok_step)]
        runner = PipelineRunner(steps, RunOptions())
        result = runner.run()
        # Should not raise
        runner.print_summary(result)
