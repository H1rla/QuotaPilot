"""Operational status and Waybar privacy/fallback behavior."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import BudgetConfig, BudgetState
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
from quotapilot.observability.models import SnapshotSource
from quotapilot.services.status import StatusService, waybar_payload

runner = CliRunner()
NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _snapshot(
    *,
    used: float | None = 0.45,
    remaining: float | None = 0.55,
    timing: bool = True,
    captured_at: datetime = NOW,
) -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            account_id="raw-private-status-account",
            plan_name="private-status-plan",
            capabilities=CapabilitySet(
                models=(
                    AIModel(
                        id="gpt-5.6-luna",
                        provider="openai-codex",
                        supported_efforts=("low", "medium", "high", "xhigh", "max"),
                    ),
                ),
            ),
            observed_at=captured_at,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="openai-codex",
                kind="unknown",
                scope="unknown",
                used_fraction=used,
                remaining_fraction=remaining,
                starts_at=NOW - timedelta(days=1) if timing else None,
                resets_at=NOW + timedelta(days=1) if timing else None,
                window_seconds=2 * 86_400 if timing else None,
                raw_name="Weekly quota",
                metadata={"raw_observation": {"account_id": "REDACTED"}},
            ),
        ),
        quota_bindings=(),
        captured_at=captured_at,
        metadata={"raw_observation": {"accountId": "REDACTED"}},
    )


def _service(repository: SqliteSnapshotRepository, *, stale: int = 900) -> StatusService:
    return StatusService(
        repository,
        BudgetEngine(BudgetConfig(stale_after_seconds=stale)),
        CapabilityEnricher(),
        ModelProfileRegistry.from_directory(default_profile_directory()),
    )


async def _save(repository: SqliteSnapshotRepository, snapshot: UsageSnapshot) -> None:
    await repository.save_snapshot(snapshot)


def test_status_normal_unknown_stale_and_no_snapshot(tmp_path: Path) -> None:
    normal_repo = SqliteSnapshotRepository(tmp_path / "normal.db")
    unknown_repo = SqliteSnapshotRepository(tmp_path / "unknown.db")
    stale_repo = SqliteSnapshotRepository(tmp_path / "stale.db")
    asyncio.run(_save(normal_repo, _snapshot()))
    asyncio.run(_save(unknown_repo, _snapshot(timing=False)))
    asyncio.run(
        _save(stale_repo, _snapshot(captured_at=NOW - timedelta(hours=2)))
    )

    normal = asyncio.run(_service(normal_repo).get_status(now=NOW))
    unknown = asyncio.run(_service(unknown_repo).get_status(now=NOW))
    stale = asyncio.run(_service(stale_repo).get_status(now=NOW))
    empty = asyncio.run(
        _service(SqliteSnapshotRepository(tmp_path / "empty.db")).get_status(now=NOW)
    )

    assert normal is not None and normal.pools[0].state is BudgetState.ON_TRACK
    assert unknown is not None and unknown.pools[0].state is BudgetState.UNKNOWN
    assert stale is not None and stale.is_stale is True
    assert empty is None


def test_provider_failure_uses_labeled_persisted_fallback(tmp_path: Path) -> None:
    class FailingProvider:
        async def capture_usage(self) -> UsageSnapshot:
            raise RuntimeError("secret provider detail")

    repository = SqliteSnapshotRepository(tmp_path / "fallback.db")
    asyncio.run(_save(repository, _snapshot()))

    report = asyncio.run(
        _service(repository).get_status(now=NOW, refresh_provider=FailingProvider())
    )

    assert report is not None
    assert report.source is SnapshotSource.PERSISTED_FALLBACK
    assert "provider_refresh_failed_using_persisted_snapshot" in report.warnings
    assert "secret provider detail" not in report.model_dump_json()


def test_status_json_is_private_and_preserves_zero_vs_null(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    asyncio.run(
        SqliteSnapshotRepository().save_snapshot(
            _snapshot(used=0.0, remaining=1.0, timing=False)
        )
    )

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["pools"][0]["used_fraction"] == 0.0
    assert payload["pools"][0]["today_budget_fraction"] is None
    assert payload["pools"][0]["state"] == "unknown"
    assert "raw-private-status-account" not in result.output
    assert "private-status-plan" not in result.output
    assert "raw_observation" not in result.output


def test_status_json_no_snapshot_is_stable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"error": "no_snapshot"}


@pytest.mark.parametrize(
    ("used", "expected_class"),
    [(0.45, "on-track"), (0.90, "critical")],
)
def test_waybar_uses_budget_state_classes(
    tmp_path: Path,
    used: float,
    expected_class: str,
) -> None:
    repository = SqliteSnapshotRepository(tmp_path / f"{expected_class}.db")
    asyncio.run(_save(repository, _snapshot(used=used, remaining=1.0 - used)))
    report = asyncio.run(_service(repository).get_status(now=NOW))

    assert report is not None
    payload = json.loads(waybar_payload(report).model_dump_json(by_alias=True))
    assert payload["class"] == expected_class
    assert payload["text"].startswith("QP ")
    assert "raw-private-status-account" not in payload["tooltip"]


def test_waybar_stale_and_error_are_always_valid_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    error_result = runner.invoke(app, ["waybar"])
    assert error_result.exit_code == 0
    assert json.loads(error_result.stdout)["class"] == "error"

    asyncio.run(
        SqliteSnapshotRepository().save_snapshot(
            _snapshot(captured_at=datetime.now(UTC) - timedelta(hours=2))
        )
    )
    stale_result = runner.invoke(app, ["waybar"])
    assert stale_result.exit_code == 0
    assert json.loads(stale_result.stdout)["class"] == "stale"


def test_waybar_unknown_is_not_rendered_as_safe(tmp_path: Path) -> None:
    repository = SqliteSnapshotRepository(tmp_path / "unknown-waybar.db")
    asyncio.run(_save(repository, _snapshot(timing=False)))
    report = asyncio.run(_service(repository).get_status(now=NOW))

    assert report is not None
    payload = json.loads(waybar_payload(report).model_dump_json(by_alias=True))
    assert payload["class"] == "unknown"
    assert "State: UNKNOWN" in payload["tooltip"]
