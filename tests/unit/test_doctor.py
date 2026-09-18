"""Structured diagnostics remain actionable and secret-safe."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quotapilot.cli.app import app
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository

runner = CliRunner()


def _check(payload: dict[str, object], name: str) -> dict[str, object]:
    checks = payload["checks"]
    assert isinstance(checks, list)
    return next(item for item in checks if item["name"] == name)


def test_doctor_reports_offline_system_without_codex(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr("quotapilot.observability.doctor.shutil.which", lambda _name: None)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["healthy"] is True
    assert _check(payload, "database")["status"] == "PASS"
    assert _check(payload, "codex_executable")["status"] == "WARN"
    assert _check(payload, "provider_capture")["status"] == "SKIP"
    assert _check(payload, "waybar")["status"] == "PASS"


def test_doctor_reports_available_codex_and_routable_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(
        "quotapilot.observability.doctor.shutil.which",
        lambda _name: "/usr/bin/codex",
    )
    monkeypatch.setattr(
        "quotapilot.observability.doctor.DoctorService._run",
        staticmethod(lambda *_args, **_kwargs: "codex-cli 0.test"),
    )
    now = datetime.now(UTC)
    snapshot = UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            capabilities=CapabilitySet(
                models=(
                    AIModel(
                        id="gpt-5.6-luna",
                        provider="openai-codex",
                        supported_efforts=("low", "medium", "high", "xhigh", "max"),
                    ),
                )
            ),
            observed_at=now,
        ),
        quota_pools=(),
        quota_bindings=(),
        captured_at=now,
    )
    asyncio.run(SqliteSnapshotRepository().save_snapshot(snapshot))

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert _check(payload, "codex_executable")["status"] == "PASS"
    assert _check(payload, "codex_version")["status"] == "PASS"
    assert _check(payload, "authentication")["status"] == "PASS"
    assert _check(payload, "app_server")["status"] == "PASS"
    assert _check(payload, "routable_models")["status"] == "PASS"


def test_doctor_invalid_config_is_structured_failure(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("budget:\n  stale_after_seconds: true\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", "--json", "--config", str(path)])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["healthy"] is False
    assert payload["checks"][0]["name"] == "configuration"
    assert payload["checks"][0]["status"] == "FAIL"


def test_doctor_never_prints_secret_looking_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret_values = (
        "qp-test-access-token-123",
        "qp-test-api-key-456",
        "qp-test-authorization-789",
        "qp-test-account-id-000",
    )
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_ACCESS_TOKEN", secret_values[0])
    monkeypatch.setenv("OPENAI_API_KEY", secret_values[1])
    monkeypatch.setenv("AUTHORIZATION", secret_values[2])
    monkeypatch.setenv("ACCOUNT_ID", secret_values[3])
    monkeypatch.setattr("quotapilot.observability.doctor.shutil.which", lambda _name: None)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    assert all(secret not in result.output for secret in secret_values)


def test_doctor_reports_database_failure_without_sql_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"database:\n  path: {json.dumps(str(tmp_path))}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("quotapilot.observability.doctor.shutil.which", lambda _name: None)

    result = runner.invoke(app, ["doctor", "--json", "--config", str(config_path)])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    database = _check(payload, "database")
    assert database["status"] == "FAIL"
    assert "SELECT" not in result.output


def test_doctor_warns_when_no_model_is_routable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr("quotapilot.observability.doctor.shutil.which", lambda _name: None)
    now = datetime.now(UTC)
    snapshot = UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            capabilities=CapabilitySet(
                models=(
                    AIModel(
                        id="unprofiled-future-model",
                        provider="openai-codex",
                    ),
                )
            ),
            observed_at=now,
        ),
        quota_pools=(),
        quota_bindings=(),
        captured_at=now,
    )
    asyncio.run(SqliteSnapshotRepository().save_snapshot(snapshot))

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    routable = _check(json.loads(result.stdout), "routable_models")
    assert routable["status"] == "WARN"
    message = routable["message"]
    assert isinstance(message, str)
    assert message.startswith("0 selectable model")


def test_doctor_reports_stale_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "stale.yaml").write_text(
        """
schema_version: 1
provider: openai-codex
product: codex
verified_at: 2020-01-01
expires_after_days: 1
models:
  synthetic-model:
    relative_power: 0.5
    provenance:
      source: manual
      confidence: provisional
      evidence: ["Synthetic doctor fixture."]
""",
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"profiles:\n  directory: {json.dumps(str(profile_dir))}\n"
        f"database:\n  path: {json.dumps(str(tmp_path / 'doctor.db'))}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("quotapilot.observability.doctor.shutil.which", lambda _name: None)

    result = runner.invoke(app, ["doctor", "--json", "--config", str(config_path)])

    assert result.exit_code == 0
    profiles = _check(json.loads(result.stdout), "model_profiles")
    assert profiles["status"] == "WARN"
    message = profiles["message"]
    assert isinstance(message, str)
    assert "stale" in message
