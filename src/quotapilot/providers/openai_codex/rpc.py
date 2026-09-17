"""Minimal JSON-RPC client for `codex app-server`'s stdio transport.

See `app_server.py` for the verified wire format this client assumes.

Once the connection dies (EOF, malformed JSON, a write/read I/O failure),
every currently-pending request fails immediately with
`AppServerTransportError`, and any *new* `request()` call fails immediately
with the same stored error rather than hanging until an external timeout.
"""

from __future__ import annotations

import asyncio
import json
from itertools import count
from typing import Any, Final

from quotapilot.providers.openai_codex.app_server import AppServerProcess


class AppServerRpcError(Exception):
    """Raised when `codex app-server` returns a JSON-RPC error response.

    This means the transport is healthy — a well-formed message came back —
    but the specific call failed. Distinct from `AppServerTransportError`.
    """

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"app-server error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class AppServerTransportError(Exception):
    """The app-server connection failed at the framing/transport level.

    Covers EOF (stdout closed), malformed JSON on a line, and I/O errors
    reading or writing the pipes. Once raised, the client is considered
    closed: further `request()` calls fail immediately with this same
    error rather than writing into a dead pipe and hanging.
    """


class OmittedType:
    """Sentinel type distinguishing 'no params key at all' from `params=None`."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "OMITTED"


OMITTED: Final = OmittedType()


class AppServerClient:
    """Correlates requests/responses and queues notifications for one process.

    Call `start_reading()` once the process is running, and `stop_reading()`
    before/while tearing it down.
    """

    def __init__(self, process: AppServerProcess) -> None:
        self._process = process
        self._ids = count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._closed_exc: Exception | None = None

    def start_reading(self) -> None:
        if self._reader_task is None:
            self._reader_task = asyncio.ensure_future(self._read_loop())

    async def stop_reading(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._pending:
            self._close_with_error(AppServerTransportError("app-server reader stopped"))

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None | OmittedType = OMITTED,
    ) -> Any:
        """Send a request. `params`:

        - `OMITTED` (default): the `"params"` key is left out of the envelope.
        - `None`: the envelope carries an explicit `"params": null`.
        - a `dict` (including `{}`): the envelope carries that object.
        """
        if self._closed_exc is not None:
            raise self._closed_exc

        request_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params is not OMITTED:
            payload["params"] = params

        try:
            self._process.stdin.write((json.dumps(payload) + "\n").encode())
            await self._process.stdin.drain()
        except (OSError, ValueError) as exc:
            self._pending.pop(request_id, None)
            future.cancel()
            transport_error = AppServerTransportError(
                f"failed to write {method!r} request to app-server stdin: {exc}"
            )
            self._close_with_error(transport_error)
            raise transport_error from exc

        try:
            return await future
        finally:
            self._pending.pop(request_id, None)

    async def next_notification(self) -> dict[str, Any]:
        return await self._notifications.get()

    async def _read_loop(self) -> None:
        try:
            while True:
                try:
                    line = await self._process.stdout.readline()
                except (OSError, ValueError) as exc:
                    self._close_with_error(
                        AppServerTransportError(f"failed to read app-server stdout: {exc}")
                    )
                    return
                if not line:
                    self._close_with_error(
                        AppServerTransportError("app-server closed its stdout (EOF)")
                    )
                    return
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._close_with_error(
                        AppServerTransportError(f"malformed JSON from app-server: {exc}")
                    )
                    return
                validated = self._validate_message(message)
                if validated is None:
                    return
                self._dispatch(validated)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # No implementation bug in the reader may strand pending callers.
            # Keep the externally visible error typed and avoid echoing an
            # arbitrary provider payload into diagnostics.
            self._close_with_error(
                AppServerTransportError(
                    f"app-server reader failed unexpectedly ({type(exc).__name__})"
                )
            )

    def _validate_message(self, value: object) -> dict[str, Any] | None:
        """Validate the minimal verified app-server response envelope.

        Codex's stdio protocol omits the usual ``jsonrpc`` member, but a
        decoded JSON value must still be an object. Responses carry an
        integer ``id`` and exactly one of ``result`` or a structured
        ``error``; notifications omit ``id`` and carry a string ``method``.
        Invalid input closes the connection immediately so no request can
        degrade into an unrelated timeout or ``AttributeError``.
        """
        if not isinstance(value, dict):
            self._close_with_error(
                AppServerTransportError("app-server message must be a JSON object")
            )
            return None

        message: dict[str, Any] = value
        if "id" not in message:
            if (
                not isinstance(message.get("method"), str)
                or "result" in message
                or "error" in message
            ):
                self._close_with_error(
                    AppServerTransportError("invalid app-server notification envelope")
                )
                return None
            return message

        message_id = message["id"]
        if type(message_id) is not int:  # bool is an int subclass, but not a valid request id.
            self._close_with_error(
                AppServerTransportError("invalid app-server response id")
            )
            return None

        has_result = "result" in message
        has_error = "error" in message
        if has_result == has_error:
            self._close_with_error(
                AppServerTransportError(
                    "app-server response must contain exactly one of result or error"
                )
            )
            return None

        if has_error:
            error = message["error"]
            if (
                not isinstance(error, dict)
                or type(error.get("code")) is not int
                or not isinstance(error.get("message"), str)
            ):
                self._close_with_error(
                    AppServerTransportError("invalid app-server error envelope")
                )
                return None

        return message

    def _close_with_error(self, exc: Exception) -> None:
        """Fail every pending request immediately and remember `exc` for
        any future `request()` call, so callers never fall back to a
        generic timeout to learn the connection is dead."""
        if self._closed_exc is None:
            self._closed_exc = exc
        stored_exc = self._closed_exc
        pending = list(self._pending.items())
        self._pending.clear()
        for _, future in pending:
            if not future.done():
                future.set_exception(stored_exc)

    def _dispatch(self, message: dict[str, Any]) -> None:
        message_id = message.get("id")
        future = self._pending.get(message_id) if message_id is not None else None
        if future is None:
            self._notifications.put_nowait(message)
            return
        if "error" in message:
            error = message["error"]
            future.set_exception(
                AppServerRpcError(
                    error["code"], error["message"], error.get("data")
                )
            )
        else:
            future.set_result(message.get("result"))
