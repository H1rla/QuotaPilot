from pathlib import Path

import pytest
from typer.testing import CliRunner

from quotapilot import __version__
from quotapilot.cli.app import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "quotapilot" in result.output.lower()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_cli_snapshot_help() -> None:
    result = runner.invoke(app, ["snapshot", "--help"])

    assert result.exit_code == 0
    assert "capture" in result.output
    assert "latest" in result.output


def test_cli_snapshot_latest_with_no_stored_snapshots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    result = runner.invoke(app, ["snapshot", "latest"])

    assert result.exit_code == 1
    assert "no snapshots stored yet" in result.output
