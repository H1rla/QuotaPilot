"""User-visible advisory route command tests using temporary SQLite."""

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
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository

runner = CliRunner()


def _seed_snapshot(*, routable: bool = True) -> tuple[str, str]:
    now = datetime.now(UTC)
    account_id = "raw-private-route-account-id"
    plan_name = "private-route-plan"
    model = AIModel(
        id="discovered-model",
        provider="test-provider",
        selectable=True,
        supported_efforts=("normal", "deep"),
        effort_order=("normal", "deep"),
        relative_power=0.75 if routable else None,
        relative_cost=0.40 if routable else None,
        relative_latency=0.30 if routable else None,
    )
    snapshot = UsageSnapshot(
        account=AccountInfo(
            provider="test-provider",
            account_id=account_id,
            plan_name=plan_name,
            capabilities=CapabilitySet(models=(model,), supports_model_selection=True),
            observed_at=now,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="test-provider",
                kind="unknown",
                scope="unknown",
                used_fraction=0.4,
                remaining_fraction=0.6,
                starts_at=now - timedelta(days=2),
                resets_at=now + timedelta(days=5),
                window_seconds=7 * 86_400,
            ),
        ),
        quota_bindings=(),
        captured_at=now,
    )
    asyncio.run(SqliteSnapshotRepository().save_snapshot(snapshot))
    return account_id, plan_name


def test_route_help() -> None:
    result = runner.invoke(
        app,
        ["route", "--help"],
        env={"FORCE_COLOR": "1", "NO_COLOR": None},
    )
    output = Text.from_ansi(result.output).plain

    assert result.exit_code == 0
    assert "--json" in output
    assert "--failure-cost" in output
    assert "--task-class" in output


def test_route_json_is_recommendation_and_excludes_account_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    account_id, plan_name = _seed_snapshot()

    result = runner.invoke(
        app,
        [
            "route",
            "Implement a local parser helper",
            "--complexity",
            "0.6",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["selected_model_id"] == "discovered-model"
    assert payload["task_profile"]["profile_source"] == "mixed"
    assert payload["selected_effort"] in {"normal", "deep"}
    assert account_id not in result.output
    assert plan_name not in result.output
    assert "account_id" not in result.output


def test_route_human_output_is_explainable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _seed_snapshot()

    result = runner.invoke(app, ["route", "Fix typo in README"])

    assert result.exit_code == 0, result.output
    assert "QuotaPilot Route" in result.output
    assert "Recommended" in result.output
    assert "Why" in result.output
    assert "Escalation" in result.output


def test_route_no_snapshot_is_stable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    result = runner.invoke(app, ["route", "Fix typo", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output) == {"error": "no_snapshot"}


def test_route_no_routable_model_is_clean_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _seed_snapshot(routable=False)

    result = runner.invoke(app, ["route", "Fix typo", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "routing_unavailable"
    assert "No routable model" in payload["message"]


def test_route_invalid_override_is_a_clean_cli_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    result = runner.invoke(app, ["route", "Task", "--complexity", "1.5"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output


def test_route_blank_task_is_a_clean_cli_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _seed_snapshot()

    result = runner.invoke(app, ["route", "   ", "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["error"] == "invalid_task_profile"
