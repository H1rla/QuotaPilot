"""CLI and service integration for profile observability and enrichment."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rich.text import Text
from typer.testing import CliRunner

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.cli.app import app
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.routing import RoutingService

runner = CliRunner()
NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _snapshot() -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            account_id="private-account-id",
            plan_name="private-plan",
            capabilities=CapabilitySet(
                models=(
                    AIModel(
                        id="gpt-5.6-luna",
                        provider="openai-codex",
                        supported_efforts=("low", "medium", "high", "xhigh", "max"),
                    ),
                    AIModel(
                        id="future-unknown-model",
                        provider="openai-codex",
                        supported_efforts=("medium",),
                    ),
                ),
                supports_model_selection=True,
            ),
            observed_at=NOW,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="openai-codex",
                kind="unknown",
                scope="unknown",
                used_fraction=0.4,
                remaining_fraction=0.6,
                starts_at=NOW - timedelta(days=2),
                resets_at=NOW + timedelta(days=5),
                window_seconds=7 * 86_400,
            ),
        ),
        quota_bindings=(),
        captured_at=NOW,
    )


def _save_snapshot() -> SqliteSnapshotRepository:
    repository = SqliteSnapshotRepository()
    asyncio.run(repository.save_snapshot(_snapshot()))
    return repository


def test_models_help_and_no_snapshot_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    help_result = runner.invoke(
        app,
        ["models", "--help"],
        env={"FORCE_COLOR": "1", "NO_COLOR": None},
    )
    help_output = Text.from_ansi(help_result.output).plain
    empty_result = runner.invoke(app, ["models", "--json"])

    assert help_result.exit_code == 0
    assert "--as-of" in help_output
    assert empty_result.exit_code == 1
    assert json.loads(empty_result.output) == {"error": "no_snapshot"}


def test_models_json_is_private_exact_and_freshness_aware(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _save_snapshot()

    fresh = runner.invoke(
        app, ["models", "--json", "--as-of", "2026-09-18"]
    )
    stale = runner.invoke(
        app, ["models", "--json", "--as-of", "2027-04-01"]
    )

    assert fresh.exit_code == 0, fresh.output
    payload = json.loads(fresh.output)
    by_id = {model["model_id"]: model for model in payload["models"]}
    assert by_id["gpt-5.6-luna"]["routable"] is True
    assert by_id["gpt-5.6-luna"]["profile_name"] == "openai_codex.yaml"
    assert by_id["gpt-5.6-luna"]["profile_source"] == "manual"
    assert by_id["gpt-5.6-luna"]["profile_evidence"]
    assert by_id["gpt-5.6-luna"]["freshness"] == "fresh"
    assert by_id["future-unknown-model"]["routable"] is False
    assert "private-account-id" not in fresh.output
    assert "private-plan" not in fresh.output

    assert stale.exit_code == 0, stale.output
    stale_payload = json.loads(stale.output)
    stale_luna = next(
        model
        for model in stale_payload["models"]
        if model["model_id"] == "gpt-5.6-luna"
    )
    assert stale_luna["routable"] is False
    assert stale_luna["freshness"] == "stale"


def test_calibration_cli_reports_component_metrics() -> None:
    help_result = runner.invoke(app, ["calibrate", "evaluate", "--help"])
    result = runner.invoke(app, ["calibrate", "evaluate", "--json"])

    assert help_result.exit_code == 0
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["metrics"]["scenario_count"] == 10
    assert payload["metrics"]["acceptable_hits"] == 10
    assert payload["metrics"]["anti_waste_violations"] == 0
    assert payload["metrics"]["capability_floor_violations"] == 0


def test_routing_service_enriches_and_exposes_local_profile_provenance(
    tmp_path: Path,
) -> None:
    repository = SqliteSnapshotRepository(tmp_path / "routing.db")
    asyncio.run(repository.save_snapshot(_snapshot()))
    service = RoutingService(
        repository,
        BudgetEngine(),
        RoutingEngine(),
        TaskProfiler(),
        CapabilityEnricher(),
        ModelProfileRegistry.from_directory(default_profile_directory()),
    )

    recommendation = asyncio.run(
        service.recommend_latest("Fix typo in README", now=NOW)
    )

    assert recommendation is not None
    assert recommendation.selected_model_id == "gpt-5.6-luna"
    assert any(
        "Capability metadata came from the versioned local profile" in line
        for line in recommendation.explanation
    )
    assert "capability_metadata_from_local_profile:provisional" in (
        recommendation.warnings
    )
