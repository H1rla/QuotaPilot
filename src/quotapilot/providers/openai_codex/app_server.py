"""Process lifecycle management for the `codex app-server` subprocess.

Wire format verified by direct observation against codex-cli 0.154.0 (see
`docs/DECISIONS.md`): the default `stdio://` transport is newline-delimited
JSON, one object per line, with no `Content-Length` framing and no top-level
`"jsonrpc"` field. Server-initiated messages (notifications) omit `"id"`;
responses to our requests echo the request's `"id"`.
"""

from __future__ import annotations

import asyncio
import collections
from collections.abc import Sequence
from types import TracebackType

_STDERR_TAIL_LINES = 20


class AppServerNotRunningError(RuntimeError):
    """Raised when an operation requires a running app-server process."""


class AppServerProcess:
    """Manages the lifecycle of a `codex app-server` subprocess (stdio transport).

    Child stderr is continuously drained in the background for the whole
    process lifetime (never left unread) — an unread stderr pipe can fill
    its OS buffer and deadlock the child the moment it logs enough output,
    regardless of whether QuotaPilot is otherwise idle. The last
    `_STDERR_TAIL_LINES` lines are kept (bounded memory) for future
    diagnostics; nothing about lifecycle (ephemeral vs. long-lived) is
    decided by this.
    """

    def __init__(
        self,
        *,
        executable: str = "codex",
        args: Sequence[str] = ("app-server",),
    ) -> None:
        self._executable = executable
        self._args = tuple(args)
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail: collections.deque[bytes] = collections.deque(
            maxlen=_STDERR_TAIL_LINES
        )

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def stdin(self) -> asyncio.StreamWriter:
        if self._process is None or self._process.stdin is None:
            raise AppServerNotRunningError("app-server is not running")
        return self._process.stdin

    @property
    def stdout(self) -> asyncio.StreamReader:
        if self._process is None or self._process.stdout is None:
            raise AppServerNotRunningError("app-server is not running")
        return self._process.stdout

    def stderr_tail_text(self) -> str:
        """The last few lines the process wrote to stderr, for diagnostics."""
        return b"".join(self._stderr_tail).decode(errors="replace")

    async def start(self) -> None:
        if self.is_running:
            return
        self._process = await asyncio.create_subprocess_exec(
            self._executable,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._stderr_task = asyncio.ensure_future(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    return
                self._stderr_tail.append(line)
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError):
            # Draining is best-effort diagnostics only; never let a stderr
            # read failure crash process management.
            return

    async def stop(self) -> None:
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None
        self._process = None

    async def __aenter__(self) -> AppServerProcess:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()
