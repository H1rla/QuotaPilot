"""Transport-foundation tests.

These exercise `AppServerProcess`/`AppServerClient` against small fake
stdio JSON-RPC peers (not the real `codex` binary), so CI does not need
Codex installed or authenticated.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from quotapilot.providers.openai_codex.app_server import (
    AppServerNotRunningError,
    AppServerProcess,
)
from quotapilot.providers.openai_codex.rpc import (
    OMITTED,
    AppServerClient,
    AppServerRpcError,
    AppServerTransportError,
)

_FAKE_PEER_SCRIPT = """
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    if message.get("method") == "boom":
        response = {
            "id": message["id"],
            "error": {"code": -32000, "message": "boom failed"},
        }
    else:
        response = {"id": message["id"], "result": {"echoed": message.get("params")}}
    sys.stdout.write(json.dumps(response) + "\\n")
    sys.stdout.flush()
    sys.stdout.write(json.dumps({"method": "heartbeat", "params": {"n": 1}}) + "\\n")
    sys.stdout.flush()
"""

# Echoes back whether the envelope had a "params" key at all, and its value.
_ENVELOPE_INSPECTING_PEER_SCRIPT = """
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    response = {
        "id": message["id"],
        "result": {
            "params_present": "params" in message,
            "params_value": message.get("params", "<absent>"),
        },
    }
    sys.stdout.write(json.dumps(response) + "\\n")
    sys.stdout.flush()
"""

_EXIT_IMMEDIATELY_SCRIPT = "import sys; sys.exit(0)"

_MALFORMED_LINE_SCRIPT = """
import sys

sys.stdout.write("not json at all\\n")
sys.stdout.flush()
"""


def _raw_response_peer_script(raw_json: str) -> str:
    """Return a peer that emits one exact JSON line after receiving a request."""
    return f"""
import sys

sys.stdin.readline()
sys.stdout.write({raw_json!r} + "\\n")
sys.stdout.flush()
"""


def _fake_process(script: str = _FAKE_PEER_SCRIPT) -> AppServerProcess:
    return AppServerProcess(executable=sys.executable, args=("-c", script))


async def test_app_server_process_lifecycle() -> None:
    process = _fake_process()
    assert process.is_running is False

    await process.start()
    try:
        assert process.is_running is True
    finally:
        await process.stop()

    assert process.is_running is False


async def test_app_server_process_requires_running_for_streams() -> None:
    process = _fake_process()

    with pytest.raises(AppServerNotRunningError):
        _ = process.stdin

    with pytest.raises(AppServerNotRunningError):
        _ = process.stdout


async def test_client_request_response_roundtrip() -> None:
    async with _fake_process() as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            result = await client.request("echo", {"hello": "world"})
            assert result == {"echoed": {"hello": "world"}}
        finally:
            await client.stop_reading()


async def test_client_surfaces_rpc_error() -> None:
    async with _fake_process() as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            with pytest.raises(AppServerRpcError) as exc_info:
                await client.request("boom")
            assert exc_info.value.code == -32000
        finally:
            await client.stop_reading()


async def test_client_queues_notifications_separately_from_responses() -> None:
    async with _fake_process() as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            await client.request("echo", {"n": 1})
            notification = await client.next_notification()
            assert notification == {"method": "heartbeat", "params": {"n": 1}}
        finally:
            await client.stop_reading()


# --- params envelope semantics (omitted / null / {}) ------------------------------


async def test_params_omitted_leaves_key_out_of_envelope() -> None:
    async with _fake_process(_ENVELOPE_INSPECTING_PEER_SCRIPT) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            result = await client.request("probe")  # default is OMITTED
            assert result == {"params_present": False, "params_value": "<absent>"}

            result = await client.request("probe", OMITTED)
            assert result == {"params_present": False, "params_value": "<absent>"}
        finally:
            await client.stop_reading()


async def test_params_none_sends_explicit_json_null() -> None:
    async with _fake_process(_ENVELOPE_INSPECTING_PEER_SCRIPT) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            result = await client.request("probe", None)
            assert result == {"params_present": True, "params_value": None}
        finally:
            await client.stop_reading()


async def test_params_empty_dict_sends_empty_object() -> None:
    async with _fake_process(_ENVELOPE_INSPECTING_PEER_SCRIPT) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            result = await client.request("probe", {})
            assert result == {"params_present": True, "params_value": {}}
        finally:
            await client.stop_reading()


# --- transport failure modes -------------------------------------------------------


async def test_eof_fails_pending_request_immediately_not_as_a_timeout() -> None:
    async with _fake_process(_EXIT_IMMEDIATELY_SCRIPT) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            with pytest.raises(AppServerTransportError):
                await client.request("anything")
        finally:
            await client.stop_reading()


async def test_malformed_json_line_fails_pending_request() -> None:
    async with _fake_process(_MALFORMED_LINE_SCRIPT) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            with pytest.raises(AppServerTransportError):
                await client.request("anything")
        finally:
            await client.stop_reading()


@pytest.mark.parametrize("raw_json", ["[]", "null", '"hello"', "123"])
async def test_non_object_json_response_fails_immediately(raw_json: str) -> None:
    async with _fake_process(_raw_response_peer_script(raw_json)) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            with pytest.raises(AppServerTransportError):
                await asyncio.wait_for(client.request("anything"), timeout=1)
        finally:
            await client.stop_reading()


@pytest.mark.parametrize(
    "raw_json",
    [
        '{"id": 1}',
        '{"id": 1, "result": {}, "error": {"code": -1, "message": "bad"}}',
        '{"id": 1, "error": null}',
        '{"id": 1, "error": []}',
        '{"id": 1, "error": {"code": "-1", "message": "bad"}}',
        '{"id": 1, "error": {"code": -1}}',
    ],
)
async def test_invalid_response_envelope_fails_immediately(raw_json: str) -> None:
    async with _fake_process(_raw_response_peer_script(raw_json)) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            with pytest.raises(AppServerTransportError):
                await asyncio.wait_for(client.request("anything"), timeout=1)
        finally:
            await client.stop_reading()


async def test_request_after_close_fails_immediately_without_writing() -> None:
    async with _fake_process(_EXIT_IMMEDIATELY_SCRIPT) as process:
        client = AppServerClient(process)
        client.start_reading()
        try:
            with pytest.raises(AppServerTransportError):
                await client.request("first")
            # The connection is already known-dead; this must not hang or
            # attempt a write into a closed pipe.
            with pytest.raises(AppServerTransportError):
                await client.request("second")
        finally:
            await client.stop_reading()
