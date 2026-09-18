"""Bounded, shell-free non-interactive adapter for current Codex CLI."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from quotapilot.execution.models import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    FailureClass,
    execution_event,
)
from quotapilot.execution.redaction import redact_output


class _InputWriter(Protocol):
    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...

    def close(self) -> None: ...

    async def wait_closed(self) -> None: ...


class _ManagedProcess(Protocol):
    @property
    def stdin(self) -> _InputWriter | None: ...

    @property
    def stdout(self) -> asyncio.StreamReader | None: ...

    @property
    def stderr(self) -> asyncio.StreamReader | None: ...

    @property
    def returncode(self) -> int | None: ...

    async def wait(self) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


ProcessFactory = Callable[
    [tuple[str, ...], Path, Mapping[str, str]], Awaitable[_ManagedProcess]
]
Clock = Callable[[], datetime]


class _BoundedTail:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        self.data.extend(chunk)
        if len(self.data) > self.limit:
            del self.data[: len(self.data) - self.limit]
            self.truncated = True

    def text(self) -> str:
        redacted = redact_output(bytes(self.data).decode("utf-8", errors="replace"))
        encoded = redacted.encode("utf-8")
        if len(encoded) <= self.limit:
            return redacted
        # Redaction may expand a short assignment value. Re-bound afterward so
        # retained metadata still obeys the configured byte limit.
        return encoded[-self.limit :].decode("utf-8", errors="ignore")


class CodexCliExecutionAdapter:
    """Invoke `codex exec` with stdin prompt, explicit cwd, and bounded tails."""

    name = "codex-cli"
    provider = "openai-codex"

    def __init__(
        self,
        *,
        executable: str = "codex",
        max_output_bytes: int = 32_768,
        process_factory: ProcessFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        self.executable = executable
        self.max_output_bytes = max_output_bytes
        self._process_factory = process_factory or self._spawn
        self._clock = clock or (lambda: datetime.now(UTC))

    def command_preview(
        self,
        model_id: str,
        effort: str | None,
        working_directory: Path,
    ) -> tuple[str, ...]:
        args = [
            self.executable,
            "--ask-for-approval",
            "never",
            "exec",
            "--ephemeral",
            "--model",
            model_id,
        ]
        if effort is not None:
            args.extend(("--config", "model_reasoning_effort=" + json.dumps(effort)))
        args.extend(
            (
                "--sandbox",
                "workspace-write",
                "--cd",
                str(working_directory),
                "--color",
                "never",
                "-",
            )
        )
        return tuple(args)

    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        started = self._clock()
        stdout_tail = _BoundedTail(self.max_output_bytes)
        stderr_tail = _BoundedTail(self.max_output_bytes)
        args = self.command_preview(plan.model_id, plan.effort, plan.working_directory)

        try:
            process = await self._process_factory(
                args,
                plan.working_directory,
                dict(os.environ),
            )
        except (FileNotFoundError, PermissionError, NotADirectoryError) as exc:
            return self._failure(
                plan,
                started,
                FailureClass.EXECUTION_ENVIRONMENT,
                message=f"failed to start execution adapter: {type(exc).__name__}",
            )
        except OSError as exc:
            return self._failure(
                plan,
                started,
                FailureClass.TRANSPORT,
                message=f"execution transport failed to start: {type(exc).__name__}",
            )

        stdout_task = asyncio.create_task(self._drain(process.stdout, stdout_tail))
        stderr_task = asyncio.create_task(self._drain(process.stderr, stderr_tail))
        try:
            await self._write_task(process, plan.task_payload)
            try:
                exit_code = await asyncio.wait_for(
                    process.wait(), timeout=plan.timeout_seconds
                )
            except TimeoutError:
                await self._stop_process(process)
                await self._finish_readers(stdout_task, stderr_task)
                return self._failure(
                    plan,
                    started,
                    FailureClass.TIMEOUT,
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                    message="execution timed out",
                )
        except asyncio.CancelledError:
            await self._stop_process(process)
            await self._finish_readers(stdout_task, stderr_task)
            return self._failure(
                plan,
                started,
                FailureClass.USER_CANCELLED,
                status=ExecutionStatus.CANCELLED,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                message="execution cancelled",
            )
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            await self._stop_process(process)
            await self._finish_readers(stdout_task, stderr_task)
            return self._failure(
                plan,
                started,
                FailureClass.TRANSPORT,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                message=f"execution transport failed: {type(exc).__name__}",
            )

        read_failed = await self._finish_readers(stdout_task, stderr_task)
        if read_failed:
            return self._failure(
                plan,
                started,
                FailureClass.TRANSPORT,
                exit_code=exit_code,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                message="failed while draining execution output",
            )
        if exit_code == 0:
            finished = self._clock()
            return ExecutionResult(
                execution_id=plan.execution_id,
                task_hash=plan.task_hash,
                started_at=started,
                finished_at=finished,
                model_id=plan.model_id,
                effort=plan.effort,
                status=ExecutionStatus.SUCCEEDED,
                exit_code=exit_code,
                stdout_summary=stdout_tail.text() or None,
                stderr_summary=stderr_tail.text() or None,
                stdout_truncated=stdout_tail.truncated,
                stderr_truncated=stderr_tail.truncated,
                attempt_count=1,
                events=(
                    execution_event(plan, ExecutionStatus.RUNNING, started),
                    execution_event(plan, ExecutionStatus.SUCCEEDED, finished),
                ),
            )

        combined = stderr_tail.text() + "\n" + stdout_tail.text()
        return self._failure(
            plan,
            started,
            self._classify_nonzero(combined),
            exit_code=exit_code,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            message="Codex CLI returned a non-zero exit status",
        )

    async def _spawn(
        self,
        args: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> _ManagedProcess:
        return await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=dict(env),
        )

    @staticmethod
    async def _write_task(process: _ManagedProcess, task: str) -> None:
        if process.stdin is None:
            raise BrokenPipeError("execution adapter stdin is unavailable")
        try:
            process.stdin.write(task.encode("utf-8"))
            await process.stdin.drain()
        finally:
            process.stdin.close()
            try:
                await process.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass

    @staticmethod
    async def _drain(
        stream: asyncio.StreamReader | None,
        tail: _BoundedTail,
    ) -> bool:
        if stream is None:
            return True
        try:
            while chunk := await stream.read(4096):
                tail.append(chunk)
        except (OSError, ValueError):
            return True
        return False

    @staticmethod
    async def _finish_readers(
        stdout_task: asyncio.Task[bool],
        stderr_task: asyncio.Task[bool],
    ) -> bool:
        results = await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        return any(result is True or isinstance(result, BaseException) for result in results)

    @staticmethod
    async def _stop_process(process: _ManagedProcess) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()

    @staticmethod
    def _classify_nonzero(output: str) -> FailureClass:
        lowered = output.casefold()
        if any(
            marker in lowered
            for marker in ("authentication", "unauthorized", "login required", "401")
        ):
            return FailureClass.AUTHENTICATION
        if any(
            marker in lowered
            for marker in ("rate limit", "quota", "usage limit", "429")
        ):
            return FailureClass.QUOTA
        return FailureClass.AGENT_ERROR

    def _failure(
        self,
        plan: ExecutionPlan,
        started: datetime,
        failure_class: FailureClass,
        *,
        status: ExecutionStatus = ExecutionStatus.FAILED,
        exit_code: int | None = None,
        stdout_tail: _BoundedTail | None = None,
        stderr_tail: _BoundedTail | None = None,
        message: str,
    ) -> ExecutionResult:
        finished = self._clock()
        return ExecutionResult(
            execution_id=plan.execution_id,
            task_hash=plan.task_hash,
            started_at=started,
            finished_at=finished,
            model_id=plan.model_id,
            effort=plan.effort,
            status=status,
            exit_code=exit_code,
            stdout_summary=stdout_tail.text() or None if stdout_tail else None,
            stderr_summary=stderr_tail.text() or None if stderr_tail else None,
            stdout_truncated=stdout_tail.truncated if stdout_tail else False,
            stderr_truncated=stderr_tail.truncated if stderr_tail else False,
            failure_class=failure_class,
            attempt_count=1,
            events=(
                execution_event(plan, ExecutionStatus.RUNNING, started),
                execution_event(plan, status, finished, message),
            ),
            message=message,
        )
