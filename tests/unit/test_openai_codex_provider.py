"""End-to-end tests for `OpenAICodexProvider` against fake stdio peers.

Uses small fake Python processes (not the real `codex` binary) that answer
JSON-RPC requests, so these tests stay fully offline and credential-free
while still exercising the whole RPC -> raw model -> parser -> domain object
pipeline through the public `UsageProvider` surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from quotapilot.providers.base import ProviderAuthentication, ProviderConnection
from quotapilot.providers.openai_codex.errors import (
    CodexNormalizationError,
    CodexRpcError,
    CodexTransportError,
)
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openai_codex"

_FAKE_APP_SERVER_SCRIPT = """
import json
import sys

account_path, rate_limits_path, model_list_path = sys.argv[1:4]
account_result = json.load(open(account_path))
rate_limits_result = json.load(open(rate_limits_path))
model_list_result = json.load(open(model_list_path))

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        result = {"userAgent": "fake-app-server/0.0.0"}
    elif method == "account/read":
        result = account_result
    elif method == "account/rateLimits/read":
        result = rate_limits_result
    elif method == "model/list":
        result = model_list_result
    else:
        sys.stdout.write(json.dumps({
            "id": message["id"],
            "error": {"code": -32601, "message": "unknown method " + str(method)},
        }) + "\\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"id": message["id"], "result": result}) + "\\n")
    sys.stdout.flush()
"""

# Drives `model/list` pagination from a JSON file shaped as
# `[{"cursor_in": ..., "cursor_out": ..., "data": [...]}, ...]` (see
# tests/fixtures/openai_codex/PROVENANCE.md); everything else answers as above.
_FAKE_PAGINATING_APP_SERVER_SCRIPT = """
import json
import sys

account_path, rate_limits_path, pages_path = sys.argv[1:4]
account_result = json.load(open(account_path))
rate_limits_result = json.load(open(rate_limits_path))
pages = json.load(open(pages_path))
pages_by_cursor_in = {json.dumps(p["cursor_in"]): p for p in pages}

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        result = {"userAgent": "fake-app-server/0.0.0"}
    elif method == "account/read":
        result = account_result
    elif method == "account/rateLimits/read":
        result = rate_limits_result
    elif method == "model/list":
        cursor_in = (message.get("params") or {}).get("cursor")
        page = pages_by_cursor_in[json.dumps(cursor_in)]
        result = {
            key: value
            for key, value in page.items()
            if key not in {"cursor_in", "cursor_out"}
        }
        result["nextCursor"] = page["cursor_out"]
    else:
        sys.stdout.write(json.dumps({
            "id": message["id"],
            "error": {"code": -32601, "message": "unknown method " + str(method)},
        }) + "\\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"id": message["id"], "result": result}) + "\\n")
    sys.stdout.flush()
"""

_CRASH_AFTER_INITIALIZE_SCRIPT = """
import json
import sys

line = sys.stdin.readline()
message = json.loads(line)
sys.stdout.write(json.dumps({"id": message["id"], "result": {"userAgent": "x"}}) + "\\n")
sys.stdout.flush()
sys.exit(0)
"""

_MALFORMED_JSON_AFTER_INITIALIZE_SCRIPT = """
import json
import sys

line = sys.stdin.readline()
message = json.loads(line)
sys.stdout.write(json.dumps({"id": message["id"], "result": {"userAgent": "x"}}) + "\\n")
sys.stdout.flush()
sys.stdin.readline()
sys.stdout.write("this is not json\\n")
sys.stdout.flush()
"""

_RPC_ERROR_SCRIPT = """
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    if message.get("method") == "initialize":
        result = {"id": message["id"], "result": {"userAgent": "x"}}
    else:
        result = {
            "id": message["id"],
            "error": {
                "code": -32001,
                "message": "rate limited",
                "data": {"secret_internal_detail": "should-never-surface"},
            },
        }
    sys.stdout.write(json.dumps(result) + "\\n")
    sys.stdout.flush()
"""


def _fake_provider() -> OpenAICodexProvider:
    return OpenAICodexProvider(
        codex_executable=sys.executable,
        codex_args=(
            "-c",
            _FAKE_APP_SERVER_SCRIPT,
            str(FIXTURES / "account_read.json"),
            str(FIXTURES / "rate_limits_single_window.json"),
            str(FIXTURES / "model_list.json"),
        ),
    )


def _paginating_provider(pages_fixture: str) -> OpenAICodexProvider:
    return OpenAICodexProvider(
        codex_executable=sys.executable,
        codex_args=(
            "-c",
            _FAKE_PAGINATING_APP_SERVER_SCRIPT,
            str(FIXTURES / "account_read.json"),
            str(FIXTURES / "rate_limits_single_window.json"),
            str(FIXTURES / pages_fixture),
        ),
    )


def _script_provider(script: str) -> OpenAICodexProvider:
    return OpenAICodexProvider(
        codex_executable=sys.executable,
        codex_args=("-c", script),
    )


# --- atomic capture --------------------------------------------------------------


async def test_capture_usage_is_one_coherent_snapshot() -> None:
    provider = _fake_provider()

    snapshot = await provider.capture_usage()

    assert snapshot.account.observed_at == snapshot.captured_at
    assert len(snapshot.quota_pools) == 1
    pool_ids = {p.id for p in snapshot.quota_pools}
    for binding in snapshot.quota_bindings:
        assert set(binding.quota_pool_ids) <= pool_ids


async def test_capture_usage_preserves_unknown_top_level_fields_in_metadata() -> None:
    provider = _fake_provider()

    snapshot = await provider.capture_usage()

    raw_observation = snapshot.metadata["raw_observation"]
    # accountId is redacted even though AccountInfo.account_id carries the
    # real (test-fake) value in its own structured field.
    assert raw_observation["rate_limits_read"]["accountId"] == "REDACTED"
    assert "rateLimitResetCredits" in raw_observation["rate_limits_read"]


async def test_get_account_get_quota_pools_get_quota_bindings_delegate_to_capture() -> None:
    provider = _fake_provider()

    account = await provider.get_account()
    pools = await provider.get_quota_pools()
    bindings = await provider.get_quota_bindings()

    assert account.provider == "openai-codex"
    assert len(pools) == 1
    assert bindings == []


async def test_get_models_round_trip_through_fake_peer() -> None:
    provider = _fake_provider()

    models = await provider.get_models()

    assert {m.id for m in models} == {
        "gpt-6-astra",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-daybreak-blue-latest",
        "gpt-5.5",
    }


def test_snapshot_coherence_check_rejects_dangling_binding() -> None:
    from quotapilot.domain.quota import QuotaBinding, QuotaPool

    pool = QuotaPool(id="known:primary", provider="openai-codex", kind="unknown", scope="unknown")
    dangling_binding = QuotaBinding(
        model_id="some-model",
        quota_pool_ids=("known:primary", "does-not-exist:primary"),
        confidence="observed",
    )

    with pytest.raises(CodexNormalizationError):
        OpenAICodexProvider._check_snapshot_coherence([pool], [dangling_binding])

    # A binding that only references known pools must not raise.
    valid_binding = QuotaBinding(
        model_id="some-model",
        quota_pool_ids=("known:primary",),
        confidence="observed",
    )
    OpenAICodexProvider._check_snapshot_coherence([pool], [valid_binding])


# --- pagination -------------------------------------------------------------------


async def test_model_list_pagination_collects_all_pages() -> None:
    provider = _paginating_provider("model_list_pages.json")

    models = await provider.get_models()

    ids = {m.id for m in models}
    assert ids == {"gpt-page1-model", "gpt-page2-model-unseen"}
    page2_model = next(m for m in models if m.id == "gpt-page2-model-unseen")
    assert "ultra_experimental" in page2_model.supported_efforts


async def test_capture_preserves_and_redacts_each_model_list_page() -> None:
    provider = _paginating_provider("model_list_pages.json")

    snapshot = await provider.capture_usage()

    pages = snapshot.metadata["raw_observation"]["model_list_pages"]
    assert [page["catalogVersion"] for page in pages] == ["synthetic-v1", "synthetic-v2"]
    assert pages[0]["nextCursor"] == "page-2-token"
    assert pages[1]["nextCursor"] is None
    assert pages[0]["accountId"] == "REDACTED"


async def test_model_list_cursor_cycle_is_detected() -> None:
    provider = _paginating_provider("model_list_cycle_pages.json")

    with pytest.raises(CodexNormalizationError):
        await provider.get_models()


# --- error taxonomy ----------------------------------------------------------------


async def test_healthcheck_ok_through_fake_peer() -> None:
    provider = _fake_provider()

    health = await provider.healthcheck()

    assert health.ok is True
    assert health.provider == "openai-codex"


async def test_healthcheck_reports_transport_error_when_executable_missing() -> None:
    provider = OpenAICodexProvider(codex_executable="quotapilot-nonexistent-binary-xyz")

    health = await provider.healthcheck()

    assert health.ok is False
    assert health.detail is not None


async def test_status_inspection_distinguishes_authentication_and_unavailable() -> None:
    authenticated = OpenAICodexProvider(
        codex_executable=sys.executable,
        codex_args=(
            "-c",
            _FAKE_APP_SERVER_SCRIPT,
            str(FIXTURES / "account_read_apikey.json"),
            str(FIXTURES / "rate_limits_single_window.json"),
            str(FIXTURES / "model_list.json"),
        ),
    )

    connected = await authenticated.inspect_status()
    not_authenticated_provider = OpenAICodexProvider(
        codex_executable=sys.executable,
        codex_args=(
            "-c",
            _FAKE_APP_SERVER_SCRIPT,
            str(FIXTURES / "account_read_null_account.json"),
            str(FIXTURES / "rate_limits_single_window.json"),
            str(FIXTURES / "model_list.json"),
        ),
    )
    authenticated_chatgpt = await _fake_provider().inspect_status()
    not_authenticated = await not_authenticated_provider.inspect_status()
    unavailable = await OpenAICodexProvider(
        codex_executable="quotapilot-nonexistent-binary-xyz"
    ).inspect_status()

    assert connected.connection is ProviderConnection.CONNECTED
    assert connected.authentication is ProviderAuthentication.AUTHENTICATED
    assert authenticated_chatgpt.authentication is ProviderAuthentication.AUTHENTICATED
    assert not_authenticated.authentication is ProviderAuthentication.NOT_AUTHENTICATED
    assert unavailable.connection is ProviderConnection.UNAVAILABLE
    assert unavailable.authentication is ProviderAuthentication.UNKNOWN


async def test_get_account_raises_transport_error_when_executable_missing() -> None:
    provider = OpenAICodexProvider(codex_executable="quotapilot-nonexistent-binary-xyz")

    with pytest.raises(CodexTransportError):
        await provider.get_account()


async def test_rpc_error_response_raises_codex_rpc_error_without_leaking_data() -> None:
    provider = _script_provider(_RPC_ERROR_SCRIPT)

    with pytest.raises(CodexRpcError) as exc_info:
        await provider.get_account()

    assert exc_info.value.code == -32001
    assert exc_info.value.method == "account/read"
    assert "secret_internal_detail" not in str(exc_info.value)
    assert "should-never-surface" not in str(exc_info.value)


async def test_process_exit_after_initialize_raises_transport_error_immediately() -> None:
    provider = _script_provider(_CRASH_AFTER_INITIALIZE_SCRIPT)

    with pytest.raises(CodexTransportError):
        await provider.get_account()


async def test_malformed_json_from_peer_raises_transport_error() -> None:
    provider = _script_provider(_MALFORMED_JSON_AFTER_INITIALIZE_SCRIPT)

    with pytest.raises(CodexTransportError):
        await provider.get_account()
