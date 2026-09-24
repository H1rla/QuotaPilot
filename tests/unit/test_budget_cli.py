"""User-visible human/JSON budget command tests using temporary SQLite."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from rich.text import Text
from typer.testing import CliRunner

from quotapilot.cli.app import app
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository

runner = CliRunner()


def _seed_snapshot(*, timing: bool = True) -> tuple[str, str]:
    now = datetime.now(UTC)
    raw_account_id = "raw-private-cli-account-id"
    plan_name = "private-plan-label"
    pool = QuotaPool(
        id="weekly",
        provider="test-provider",
        kind="unknown",
        scope="unknown",
        used_fraction=0.65,
        remaining_fraction=0.35,
        starts_at=now - timedelta(days=3) if timing else None,
        resets_at=now + timedelta(days=4) if timing else None,
        window_seconds=7 * 86_400 if timing else None,
        raw_name="Weekly quota",
    )
    snapshot = UsageSnapshot(
        account=AccountInfo(
            provider="test-provider",
            account_id=raw_account_id,
            plan_name=plan_name,
            capabilities=CapabilitySet(models=()),
            observed_at=now,
        ),
        quota_pools=(pool,),
        quota_bindings=(),
        captured_at=now,
    )
    asyncio.run(SqliteSnapshotRepository().save_snapshot(snapshot))
    return raw_account_id, plan_name


def test_budget_help() -> None:
    result = runner.invoke(
        app,
        ["budget", "--help"],
        env={"FORCE_COLOR": "1", "NO_COLOR": None},
    )
    output = Text.from_ansi(result.output).plain

    assert result.exit_code == 0
    assert "--json" in output
    assert "--reserve-fraction" in output


def test_budget_json_is_report_model_and_excludes_account_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    raw_account_id, plan_name = _seed_snapshot()

    result = runner.invoke(app, ["budget", "--json", "--stale-after-seconds", "3600"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["pools"][0]["pool_id"] == "weekly"
    assert payload["pools"][0]["actual_usage"] == 0.65
    assert payload["binding_pool_id"] == "weekly"
    assert raw_account_id not in result.output
    assert plan_name not in result.output
    assert "account_id" not in result.output


def test_budget_human_output_marks_unknown_pace_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _seed_snapshot(timing=False)

    result = runner.invoke(app, ["budget"])

    assert result.exit_code == 0
    assert "QuotaPilot Budget" in result.output
    assert "Expected by now     unavailable" in result.output
    assert "State               UNKNOWN" in result.output


def test_budget_json_no_snapshot_is_stable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    result = runner.invoke(app, ["budget", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output) == {"error": "no_snapshot"}


def test_budget_invalid_config_is_clean_cli_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    result = runner.invoke(app, ["budget", "--reserve-fraction", "1.0"])

    assert result.exit_code == 2
    assert "invalid budget configuration" in result.output
