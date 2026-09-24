"""Strict configuration loading, precedence, and privacy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quotapilot.cli.app import app
from quotapilot.config import (
    ConfigLoadError,
    ConfigValidationError,
    load_effective_config,
)
from quotapilot.config.models import LanguagePreference, TuiThemePreference
from quotapilot.execution.models import ExecutionMode

runner = CliRunner()


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_absent_config_uses_strict_defaults(tmp_path: Path) -> None:
    effective = load_effective_config(path=tmp_path / "missing.yaml", environ={})

    assert effective.file_present is False
    assert effective.config.budget.reserve_fraction == 0.10
    assert effective.config.execution.mode is ExecutionMode.ALWAYS_CONFIRM
    assert effective.config.appearance.language is LanguagePreference.SYSTEM
    assert effective.config.appearance.tui_theme is TuiThemePreference.SYSTEM
    assert effective.sources["budget.reserve_fraction"] == "policy-default"


def test_valid_config_and_source_tracking(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "config.yaml",
        """
budget:
  reserve_fraction: 0.2
  timezone: Asia/Tokyo
execution:
  mode: never_execute
appearance:
  language: ja
  tui_theme: light
""",
    )

    effective = load_effective_config(path=path, environ={})

    assert effective.config.budget.reserve_fraction == 0.2
    assert effective.config.budget.timezone == "Asia/Tokyo"
    assert effective.config.execution.mode is ExecutionMode.NEVER_EXECUTE
    assert effective.config.appearance.language is LanguagePreference.JAPANESE
    assert effective.config.appearance.tui_theme is TuiThemePreference.LIGHT
    assert effective.sources["budget.reserve_fraction"] == "user-config"


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        ("budget: [", ConfigLoadError),
        ("unknown_section: {}\n", ConfigValidationError),
        ("budget:\n  reserve_fraction: '0.2'\n", ConfigValidationError),
        ("budget:\n  reserve_fraction: true\n", ConfigValidationError),
        ("budget:\n  timezone: Mars/Olympus\n", ConfigValidationError),
        ("execution:\n  mode: maybe\n", ConfigValidationError),
        ("appearance:\n  language: klingon\n", ConfigValidationError),
        ("appearance:\n  tui_theme: sepia\n", ConfigValidationError),
    ],
)
def test_malformed_or_invalid_config_is_rejected(
    tmp_path: Path,
    content: str,
    error_type: type[Exception],
) -> None:
    path = _write(tmp_path / "config.yaml", content)

    with pytest.raises(error_type):
        load_effective_config(path=path, environ={})


def test_precedence_is_cli_over_environment_over_file(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "config.yaml",
        "budget:\n  reserve_fraction: 0.2\n  stale_after_seconds: 1200\n",
    )
    environment = {
        "QUOTAPILOT_BUDGET_RESERVE_FRACTION": "0.3",
        "QUOTAPILOT_BUDGET_STALE_AFTER_SECONDS": "1800",
    }

    effective = load_effective_config(
        path=path,
        environ=environment,
        cli_overrides={"budget.reserve_fraction": 0.4},
    )

    assert effective.config.budget.reserve_fraction == 0.4
    assert effective.config.budget.stale_after_seconds == 1800
    assert effective.sources["budget.reserve_fraction"] == "cli"
    assert effective.sources["budget.stale_after_seconds"] == "environment"


def test_config_show_is_json_and_does_not_echo_unrelated_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write(tmp_path / "config.yaml", "budget:\n  reserve_fraction: 0.2\n")
    secret = "super-secret-token-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("QUOTAPILOT_ACCESS_TOKEN", secret)

    result = runner.invoke(app, ["config", "show", "--json", "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["config"]["budget"]["reserve_fraction"] == 0.2
    assert payload["sources"]["budget.reserve_fraction"] == "user-config"
    assert secret not in result.output


def test_config_validate_invalid_file_is_clean_json(tmp_path: Path) -> None:
    path = _write(tmp_path / "config.yaml", "budget:\n  reserv_fraction: 0.8\n")

    result = runner.invoke(
        app,
        ["config", "validate", "--json", "--config", str(path)],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"] == "invalid_config"
