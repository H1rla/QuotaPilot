"""Codex CLI adapter safety, cleanup, taxonomy, and bounded-output tests."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quotapilot.budget.models import BudgetReport
from quotapilot.execution.adapters.codex_cli import CodexCliExecutionAdapter
from quotapilot.execution.models import ExecutionPolicy, ExecutionStatus, FailureClass
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.routing.models import (
    CandidateScore,
    ProfileSource,
    QuotaPressureSource,
    RecommendationConfidence,
    RoutingRecommendation,
    TaskClass,
    TaskProfile,
)

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


class _Writer:
    def __init__(self, *, broken: bool = False) -> None:
        self.data = bytearray()
        self.closed = False
        self.broken = broken

    def write(self, data: bytes) -> None:
        if self.broken:
            raise BrokenPipeError
        self.data.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class _Process:
    def __init__(
        self,
        *,
        exit_code: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        block: bool = False,
        broken_stdin: bool = False,
    ) -> None:
        self.stdin = _Writer(broken=broken_stdin)
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.stdout.feed_data(stdout)
        self.stdout.feed_eof()
        self.stderr.feed_data(stderr)
        self.stderr.feed_eof()
        self.returncode: int | None = None if block else exit_code
        self._exit_code = exit_code
        self._done = asyncio.Event()
        if not block:
            self._done.set()
        self.terminated = False
        self.killed = False

    async def wait(self) -> int:
        await self._done.wait()
        assert self.returncode is not None
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15
        self._done.set()

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9
        self._done.set()


class _Factory:
    def __init__(self, process: _Process) -> None:
        self.process = process
        self.calls: list[tuple[tuple[str, ...], Path, Mapping[str, str]]] = []

    async def __call__(
        self,
        args: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> _Process:
        self.calls.append((args, cwd, env))
        return self.process


def _recommendation() -> RoutingRecommendation:
    profile = TaskProfile(
        summary="Do not interpolate $(touch /tmp/bad) ; echo secret",
        complexity=0.2,
        ambiguity=0.1,
        failure_cost=0.1,
        verifiability=0.9,
        context_demand=0.2,
        latency_sensitivity=0.5,
        task_class=TaskClass.MECHANICAL,
        profile_source=ProfileSource.EXPLICIT,
    )
    return RoutingRecommendation(
        task_profile=profile,
        difficulty_score=0.2,
        required_power=0.2,
        capability_floor=0.1,
        effort_demand=0.2,
        quota_pressure=0.35,
        quota_pressure_source=QuotaPressureSource.BUDGET_REPORT,
        selected_model_id="model-a",
        selected_effort="normal",
        candidate_scores=(
            CandidateScore(model_id="model-a", selectable=True, eligible=True),
        ),
        escalation_path=(),
        alternatives=(),
        explanation=(),
        warnings=(),
        confidence=RecommendationConfidence.HIGH,
    )


def _plan(tmp_path: Path, *, timeout: int = 10):
    policy = ExecutionPolicy(timeout_seconds=timeout)
    budget = BudgetReport(
        captured_at=NOW,
        evaluated_at=NOW,
        snapshot_age_seconds=0.0,
        is_stale=False,
        reserve_fraction=0.1,
        timezone="UTC",
        pools=(),
        effective_pressure=0.35,
    )
    return ExecutionPlanner(policy, id_factory=lambda: "id-1").build(
        _recommendation(),
        budget,
        provider="openai-codex",
        task_payload=_recommendation().task_profile.summary,
        working_directory=tmp_path,
        dry_run=False,
        adapter_name="codex-cli",
        command_preview=("placeholder",),
        planned_at=NOW,
    )


@pytest.mark.asyncio
async def test_structured_invocation_passes_task_only_over_stdin(tmp_path: Path) -> None:
    process = _Process(stdout=b"done")
    factory = _Factory(process)
    adapter = CodexCliExecutionAdapter(process_factory=factory, clock=lambda: NOW)
    plan = _plan(tmp_path)

    result = await adapter.execute(plan)

    assert result.status is ExecutionStatus.SUCCEEDED
    args, cwd, _env = factory.calls[0]
    assert args[:4] == ("codex", "--ask-for-approval", "never", "exec")
    assert "--ephemeral" in args
    assert "--sandbox" in args and "workspace-write" in args
    assert "--cd" in args and str(tmp_path) in args
    assert plan.task_payload not in args
    assert bytes(process.stdin.data) == plan.task_payload.encode()
    assert process.stdin.closed
    assert cwd == tmp_path


@pytest.mark.asyncio
async def test_nonzero_authentication_is_structured_and_redacted(tmp_path: Path) -> None:
    process = _Process(
        exit_code=1,
        stderr=b"authentication failed Authorization: Bearer abcdefghijklmnop",
    )
    adapter = CodexCliExecutionAdapter(
        process_factory=_Factory(process), clock=lambda: NOW
    )

    result = await adapter.execute(_plan(tmp_path))

    assert result.failure_class is FailureClass.AUTHENTICATION
    assert result.status is ExecutionStatus.FAILED
    assert "abcdefghijklmnop" not in (result.stderr_summary or "")
    assert "REDACTED" in (result.stderr_summary or "")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (b"rate limit exceeded", FailureClass.QUOTA),
        (b"agent completed with an error", FailureClass.AGENT_ERROR),
    ],
)
async def test_other_nonzero_failures_keep_distinct_taxonomy(
    tmp_path: Path,
    stderr: bytes,
    expected: FailureClass,
) -> None:
    adapter = CodexCliExecutionAdapter(
        process_factory=_Factory(_Process(exit_code=1, stderr=stderr)),
        clock=lambda: NOW,
    )

    result = await adapter.execute(_plan(tmp_path))

    assert result.failure_class is expected


@pytest.mark.asyncio
async def test_output_capture_keeps_only_a_bounded_tail(tmp_path: Path) -> None:
    process = _Process(stdout=b"prefix-" + b"x" * 100 + b"-tail")
    adapter = CodexCliExecutionAdapter(
        max_output_bytes=16,
        process_factory=_Factory(process),
        clock=lambda: NOW,
    )

    result = await adapter.execute(_plan(tmp_path))

    assert result.stdout_truncated
    assert result.stdout_summary is not None
    assert len(result.stdout_summary.encode()) <= 16
    assert result.stdout_summary.endswith("-tail")


@pytest.mark.asyncio
async def test_timeout_terminates_and_reaps_process(tmp_path: Path) -> None:
    process = _Process(block=True)
    ticks = iter((NOW, NOW + timedelta(seconds=1)))
    adapter = CodexCliExecutionAdapter(
        process_factory=_Factory(process), clock=lambda: next(ticks)
    )

    result = await adapter.execute(_plan(tmp_path, timeout=1))

    assert result.failure_class is FailureClass.TIMEOUT
    assert process.terminated
    assert process.returncode is not None


@pytest.mark.asyncio
async def test_cancellation_terminates_process_and_returns_cancelled(tmp_path: Path) -> None:
    process = _Process(block=True)
    ticks = iter((NOW, NOW + timedelta(seconds=1)))
    adapter = CodexCliExecutionAdapter(
        process_factory=_Factory(process), clock=lambda: next(ticks)
    )
    task = asyncio.create_task(adapter.execute(_plan(tmp_path)))
    await asyncio.sleep(0)

    task.cancel()
    result = await task

    assert result.status is ExecutionStatus.CANCELLED
    assert result.failure_class is FailureClass.USER_CANCELLED
    assert process.terminated


@pytest.mark.asyncio
async def test_broken_stdin_is_transport_failure_with_cleanup(tmp_path: Path) -> None:
    process = _Process(block=True, broken_stdin=True)
    adapter = CodexCliExecutionAdapter(
        process_factory=_Factory(process), clock=lambda: NOW
    )

    result = await adapter.execute(_plan(tmp_path))

    assert result.failure_class is FailureClass.TRANSPORT
    assert process.terminated
    assert process.stdin.closed


@pytest.mark.asyncio
async def test_missing_executable_is_execution_environment_failure(tmp_path: Path) -> None:
    async def missing(
        _args: tuple[str, ...], _cwd: Path, _env: Mapping[str, str]
    ) -> _Process:
        raise FileNotFoundError

    adapter = CodexCliExecutionAdapter(process_factory=missing, clock=lambda: NOW)

    result = await adapter.execute(_plan(tmp_path))

    assert result.failure_class is FailureClass.EXECUTION_ENVIRONMENT
    assert result.attempt_count == 1
