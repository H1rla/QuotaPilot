"""User-visible dry-run and conservative approval behavior."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rich.text import Text
from typer.testing import CliRunner

from quotapilot.cli.app import app
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository

runner = CliRunner()


def _seed_snapshot(*, age_seconds: int = 0) -> None:
    captured_at = datetime.now(UTC) - timedelta(seconds=age_seconds)
    model = AIModel(
        id="discovered-executable",
        provider="openai-codex",
        selectable=True,
        supported_efforts=("normal", "deep"),
        effort_order=("normal", "deep"),
        relative_power=0.75,
        relative_cost=0.4,
        relative_latency=0.3,
    )
    snapshot = UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            account_id="private-execution-account-id",
            plan_name="private-plan",
            capabilities=CapabilitySet(models=(model,), supports_model_selection=True),
            observed_at=captured_at,
        ),
        quota_pools=(),
        quota_bindings=(),
        captured_at=captured_at,
    )
    asyncio.run(SqliteSnapshotRepository().save_snapshot(snapshot))


def test_execute_help_documents_dry_run_and_policy() -> None:
    result = runner.invoke(
        app,
        ["execute", "--help"],
        env={"FORCE_COLOR": "1", "NO_COLOR": None},
    )
    output = Text.from_ansi(result.output).plain

    assert result.exit_code == 0
    assert "--dry-run" in output
    assert "--json" in output
    assert "--approval-mode" in output
    assert "--timeout-seconds" in output


def test_json_dry_run_is_safe_and_does_not_include_task_or_account(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    _seed_snapshot()
    task = "Private task: fix src/secret_module.py"

    result = runner.invoke(
        app,
        ["execute", task, "--dry-run", "--json", "--cwd", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["provider"] == "openai-codex"
    assert payload["adapter_name"] == "codex-cli"
    assert payload["requires_confirmation"] is False
    assert payload["task_class"]
    assert payload["task_hash"].startswith("sha256:")
    assert task not in result.output
    assert "private-execution-account-id" not in result.output
    assert "private-plan" not in result.output
    assert "task_payload" not in payload
    assert "task_profile" not in payload


def test_human_dry_run_shows_required_audit_fields(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    _seed_snapshot()

    result = runner.invoke(
        app,
        ["execute", "Fix typo in README", "--dry-run", "--cwd", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    for expected in (
        "Task class",
        "Recommended model",
        "Recommended effort",
        "Quota pressure",
        "Binding pool",
        "Execution adapter",
        "Working directory",
        "Approval required",
        "Timeout",
        "Maximum attempts",
        "Escalation path",
    ):
        assert expected in result.output


def test_dry_run_no_snapshot_and_stale_snapshot_are_clean_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "empty"))
    no_snapshot = runner.invoke(
        app, ["execute", "Fix typo", "--dry-run", "--json", "--cwd", str(tmp_path)]
    )
    assert no_snapshot.exit_code == 1
    assert json.loads(no_snapshot.output)["error"] == "execution_unavailable"
    assert "persisted snapshot" in no_snapshot.output

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "stale"))
    _seed_snapshot(age_seconds=301)
    stale = runner.invoke(
        app, ["execute", "Fix typo", "--dry-run", "--json", "--cwd", str(tmp_path)]
    )
    assert stale.exit_code == 1
    assert "stale" in json.loads(stale.output)["message"]


def test_real_execution_defaults_to_confirmation_and_decline_never_captures_live(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    _seed_snapshot()

    result = runner.invoke(
        app,
        ["execute", "Fix typo in README", "--cwd", str(tmp_path)],
        input="n\n",
    )

    assert result.exit_code == 1, result.output
    assert "Approval required   yes" in result.output
    assert "Execute this exact plan?" in result.output
    assert "Status              denied" in result.output


def test_json_is_rejected_for_real_execution() -> None:
    result = runner.invoke(app, ["execute", "Task", "--json"])

    assert result.exit_code == 2
    assert "only with --dry-run" in result.output
