"""Automated guard against committing unsanitized live provider data.

This turns the manual "grep all fixtures for email/account id/token/..."
check from the Phase 2.1 stabilization review into a permanent, always-run
test, so a future live-capture session can't accidentally commit real
telemetry again without CI catching it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openai_codex"

_ALLOWED_EMAIL_DOMAINS = {"example.invalid"}
_ACCOUNT_ID_KEYS = {"accountid", "account_id"}
_OTHER_SENSITIVE_ID_KEYS = {
    "sessionid",
    "session_id",
    "organizationid",
    "organization_id",
    "orgid",
    "org_id",
    "apikey",
    "api_key",
    "token",
    "accesstoken",
    "access_token",
    "refreshtoken",
    "refresh_token",
}


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURES.glob("*.json"))


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, str):
        yield value


def _walk_keyed_values(value: Any, keys: set[str], *, key: str | None = None) -> Iterator[str]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_keyed_values(v, keys, key=k)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keyed_values(item, keys, key=key)
    elif key is not None and key.lower() in keys and isinstance(value, str):
        yield value


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.name)
def test_fixture_has_no_real_email_domain(path: Path) -> None:
    data = json.loads(path.read_text())
    for value in _walk_strings(data):
        if "@" in value:
            domain = value.rsplit("@", 1)[-1]
            assert domain in _ALLOWED_EMAIL_DOMAINS, (
                f"{path.name} contains a non-placeholder email address: {value!r}"
            )


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.name)
def test_fixture_account_ids_are_placeholders(path: Path) -> None:
    data = json.loads(path.read_text())
    for account_id in _walk_keyed_values(data, _ACCOUNT_ID_KEYS):
        assert account_id.startswith("acct_redacted") or account_id == "REDACTED", (
            f"{path.name} has a non-placeholder account id: {account_id!r}"
        )


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.name)
def test_fixture_other_sensitive_identifiers_are_redacted(path: Path) -> None:
    data = json.loads(path.read_text())
    for value in _walk_keyed_values(data, _OTHER_SENSITIVE_ID_KEYS):
        assert value == "REDACTED" or "redacted" in value.lower(), (
            f"{path.name} has a non-placeholder sensitive identifier"
        )


def test_usage_read_fixture_is_synthetic_not_real_telemetry() -> None:
    """Regression guard: pins the known-synthetic values from the Phase 2.1
    fixture replacement (see PROVENANCE.md). If this fails, someone likely
    replaced this fixture with real usage telemetry again."""
    data = json.loads((FIXTURES / "usage_read.json").read_text())

    assert data["summary"]["lifetimeTokens"] == 4820000
    assert data["summary"]["peakDailyTokens"] == 610000


def test_account_and_rate_limit_fixtures_pin_synthetic_private_values() -> None:
    account = json.loads((FIXTURES / "account_read.json").read_text())
    rate_limits = json.loads((FIXTURES / "rate_limits_single_window.json").read_text())

    assert account["account"]["planType"] == "synthetic-plan"
    primary = rate_limits["rateLimits"]["primary"]
    assert primary["usedPercent"] == 65
    assert primary["resetsAt"] == 1893456000
    assert rate_limits["rateLimits"]["planType"] == "synthetic-plan"
