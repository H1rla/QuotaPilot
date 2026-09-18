"""Shared helper: build a real, richly-populated `UsageSnapshot` via
`OpenAICodexProvider` against a fake stdio peer (not the real `codex`
binary), reusing the exact fixtures already used by
`test_openai_codex_provider.py`.

Not a test module itself (no `test_` prefix) — pytest will not collect it.
"""

from __future__ import annotations

import sys
from pathlib import Path

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


def fake_provider(
    account_fixture: str = "account_read.json",
    rate_limits_fixture: str = "rate_limits_multi_window.json",
    model_list_fixture: str = "model_list.json",
) -> OpenAICodexProvider:
    """A provider wired to a fake stdio peer answering from fixture files.

    Defaults to `rate_limits_multi_window.json` (rather than the
    single-pool fixture) so a snapshot built from this has multiple pools
    *and* a binding by default — more representative for persistence tests.
    """
    return OpenAICodexProvider(
        codex_executable=sys.executable,
        codex_args=(
            "-c",
            _FAKE_APP_SERVER_SCRIPT,
            str(FIXTURES / account_fixture),
            str(FIXTURES / rate_limits_fixture),
            str(FIXTURES / model_list_fixture),
        ),
    )
