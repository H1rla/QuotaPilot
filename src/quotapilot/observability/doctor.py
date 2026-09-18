"""Structured local diagnostics with deliberately bounded disclosure."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher, capability_views
from quotapilot.capabilities.loader import load_profile
from quotapilot.capabilities.models import ProfileFreshness
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config.loader import EffectiveConfig
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.services.status import StatusService, waybar_error, waybar_payload


class DoctorStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class DoctorCheck(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    name: str
    status: DoctorStatus
    message: str
    remediation: str | None = None


class DoctorReport(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: int = 1
    checked_at: AwareDatetime
    healthy: bool
    checks: tuple[DoctorCheck, ...] = Field(default_factory=tuple)


def invalid_config_report(*, now: datetime) -> DoctorReport:
    """Represent config failure without echoing its potentially private values."""
    check = DoctorCheck(
        name="configuration",
        status=DoctorStatus.FAIL,
        message="configuration could not be validated",
        remediation="Run `quotapilot config validate` and correct the reported field.",
    )
    return DoctorReport(checked_at=now, healthy=False, checks=(check,))


class DoctorService:
    """Run diagnostics without exposing command output, auth data, or account identity."""

    def __init__(self, effective: EffectiveConfig) -> None:
        self._effective = effective

    async def run(self, *, now: datetime, live: bool = False) -> DoctorReport:
        checks: list[DoctorCheck] = [self._runtime_check(), self._config_check()]
        config = self._effective.config
        repository = SqliteSnapshotRepository(config.database.path)

        snapshot = None
        try:
            snapshot = await repository.get_latest_snapshot(provider=config.provider.default)
            checks.append(
                DoctorCheck(
                    name="database",
                    status=DoctorStatus.PASS,
                    message="snapshot database is writable and its schema is valid",
                )
            )
        except Exception:  # noqa: BLE001 - never reflect SQLite internals
            checks.append(
                DoctorCheck(
                    name="database",
                    status=DoctorStatus.FAIL,
                    message="snapshot database is unavailable or invalid",
                    remediation="Check the data-directory permissions and database integrity.",
                )
            )

        executable = shutil.which("codex")
        if executable is None:
            checks.extend(
                [
                    DoctorCheck(
                        name="codex_executable",
                        status=DoctorStatus.WARN,
                        message="Codex CLI was not found on PATH",
                        remediation="Install Codex CLI and ensure `codex` is on PATH.",
                    ),
                    DoctorCheck(
                        name="codex_version",
                        status=DoctorStatus.SKIP,
                        message="version check skipped because Codex CLI is unavailable",
                    ),
                    DoctorCheck(
                        name="authentication",
                        status=DoctorStatus.SKIP,
                        message="authentication check skipped because Codex CLI is unavailable",
                    ),
                    DoctorCheck(
                        name="app_server",
                        status=DoctorStatus.SKIP,
                        message="app-server check skipped because Codex CLI is unavailable",
                    ),
                    DoctorCheck(
                        name="execution_adapter",
                        status=DoctorStatus.WARN,
                        message="Codex execution adapter is unavailable",
                        remediation="Install Codex CLI before attempting real execution.",
                    ),
                ]
            )
        else:
            checks.extend(self._codex_checks(executable))

        profile_dir = (
            Path(config.profiles.directory).expanduser()
            if config.profiles.directory
            else self._bundled_profile_directory()
        )
        registry: ModelProfileRegistry | None = None
        try:
            registry = ModelProfileRegistry.from_directory(profile_dir)
            freshness = self._profile_freshness(profile_dir, now.astimezone(UTC).date())
            status = (
                DoctorStatus.WARN
                if freshness is not ProfileFreshness.FRESH
                else DoctorStatus.PASS
            )
            checks.append(
                DoctorCheck(
                    name="model_profiles",
                    status=status,
                    message=f"model profiles loaded; aggregate freshness is {freshness.value}",
                    remediation=(
                        "Review and re-verify stale or undated profile metadata."
                        if status is DoctorStatus.WARN
                        else None
                    ),
                )
            )
        except Exception:  # noqa: BLE001 - profile data is untrusted local input
            checks.append(
                DoctorCheck(
                    name="model_profiles",
                    status=DoctorStatus.FAIL,
                    message="model profiles could not be loaded",
                    remediation="Run `quotapilot config validate` and inspect the profile YAML.",
                )
            )

        if snapshot is None or registry is None:
            checks.append(
                DoctorCheck(
                    name="routable_models",
                    status=DoctorStatus.SKIP,
                    message="routable-model check requires a snapshot and valid profiles",
                )
            )
        else:
            enriched = CapabilityEnricher().enrich(
                snapshot.account.capabilities,
                registry,
                evaluated_on=now.astimezone(UTC).date(),
            )
            count = sum(view.routable for view in capability_views(enriched))
            checks.append(
                DoctorCheck(
                    name="routable_models",
                    status=DoctorStatus.PASS if count else DoctorStatus.WARN,
                    message=f"{count} selectable model(s) have sufficient routing metadata",
                    remediation=(
                        "Capture current capabilities and review exact-ID model profiles."
                        if not count
                        else None
                    ),
                )
            )

        if live:
            if config.provider.default not in {None, "openai-codex"}:
                checks.append(
                    DoctorCheck(
                        name="provider_capture",
                        status=DoctorStatus.SKIP,
                        message="no live adapter exists for the configured provider",
                    )
                )
            else:
                try:
                    captured = await OpenAICodexProvider().capture_usage()
                    checks.append(
                        DoctorCheck(
                            name="provider_capture",
                            status=DoctorStatus.PASS,
                            message=(
                                "provider capture succeeded with "
                                f"{len(captured.quota_pools)} quota pool(s)"
                            ),
                        )
                    )
                except Exception:  # noqa: BLE001 - provider errors may contain private context
                    checks.append(
                        DoctorCheck(
                            name="provider_capture",
                            status=DoctorStatus.WARN,
                            message="provider capture failed",
                            remediation=(
                                "Check Codex authentication and app-server availability."
                            ),
                        )
                    )
        else:
            checks.append(
                DoctorCheck(
                    name="provider_capture",
                    status=DoctorStatus.SKIP,
                    message="live provider capture was not requested",
                    remediation="Run `quotapilot doctor --live` for an explicit live check.",
                )
            )

        try:
            if snapshot is not None and registry is not None:
                status_service = StatusService(
                    repository,
                    BudgetEngine(config.budget),
                    CapabilityEnricher(),
                    registry,
                )
                status_report = await status_service.get_status(
                    now=now,
                    provider=config.provider.default,
                )
                payload = (
                    waybar_payload(status_report)
                    if status_report is not None
                    else waybar_error("no persisted snapshot")
                )
            else:
                payload = waybar_error("no persisted snapshot")
            payload.model_dump_json(by_alias=True)
            checks.append(
                DoctorCheck(
                    name="waybar",
                    status=DoctorStatus.PASS,
                    message="Waybar rendering produced valid privacy-safe JSON",
                )
            )
        except Exception:  # noqa: BLE001
            checks.append(
                DoctorCheck(
                    name="waybar",
                    status=DoctorStatus.FAIL,
                    message="Waybar rendering failed",
                    remediation="Inspect configuration, database, and profile diagnostics.",
                )
            )

        healthy = not any(check.status is DoctorStatus.FAIL for check in checks)
        return DoctorReport(checked_at=now, healthy=healthy, checks=tuple(checks))

    def _config_check(self) -> DoctorCheck:
        return DoctorCheck(
            name="configuration",
            status=DoctorStatus.PASS,
            message=(
                "strict user configuration is valid"
                if self._effective.file_present
                else "no user config file; strict built-in defaults are valid"
            ),
        )

    @staticmethod
    def _runtime_check() -> DoctorCheck:
        supported = sys.version_info >= (3, 12)
        return DoctorCheck(
            name="python_runtime",
            status=DoctorStatus.PASS if supported else DoctorStatus.FAIL,
            message=(
                f"Python {sys.version_info.major}.{sys.version_info.minor} "
                + ("is supported" if supported else "is unsupported")
            ),
            remediation=None if supported else "Install Python 3.12 or newer.",
        )

    @staticmethod
    def _codex_checks(executable: str) -> list[DoctorCheck]:
        checks = [
            DoctorCheck(
                name="codex_executable",
                status=DoctorStatus.PASS,
                message="Codex CLI is available on PATH",
            )
        ]
        version = DoctorService._run(executable, "--version", capture=True)
        checks.append(
            DoctorCheck(
                name="codex_version",
                status=DoctorStatus.PASS if version is not None else DoctorStatus.WARN,
                message=(
                    f"Codex CLI version: {version}"
                    if version is not None
                    else "Codex CLI version could not be determined"
                ),
            )
        )
        authenticated = DoctorService._run(executable, "login", "status") is not None
        checks.append(
            DoctorCheck(
                name="authentication",
                status=DoctorStatus.PASS if authenticated else DoctorStatus.WARN,
                message=(
                    "Codex reports authentication is available"
                    if authenticated
                    else "Codex authentication is unavailable or could not be verified"
                ),
                remediation=None if authenticated else "Run the Codex login workflow.",
            )
        )
        app_server = DoctorService._run(executable, "app-server", "--help") is not None
        checks.append(
            DoctorCheck(
                name="app_server",
                status=DoctorStatus.PASS if app_server else DoctorStatus.WARN,
                message=(
                    "Codex app-server command is available"
                    if app_server
                    else "Codex app-server command is unavailable"
                ),
            )
        )
        checks.append(
            DoctorCheck(
                name="execution_adapter",
                status=DoctorStatus.PASS,
                message="Codex execution adapter executable is available",
            )
        )
        return checks

    @staticmethod
    def _run(executable: str, *args: str, capture: bool = False) -> str | None:
        try:
            completed = subprocess.run(  # noqa: S603 - resolved executable, fixed args
                [executable, *args],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        if not capture:
            return "ok"
        # `--version` is public metadata. Bound and normalize it before display.
        return completed.stdout[:200].decode(errors="replace").strip() or None

    @staticmethod
    def _profile_freshness(directory: Path, evaluated_on: date) -> ProfileFreshness:
        paths = sorted((*directory.glob("*.yaml"), *directory.glob("*.yml")))
        values = tuple(load_profile(path).freshness(evaluated_on) for path in paths)
        if ProfileFreshness.STALE in values:
            return ProfileFreshness.STALE
        if ProfileFreshness.UNKNOWN in values or not values:
            return ProfileFreshness.UNKNOWN
        return ProfileFreshness.FRESH

    @staticmethod
    def _bundled_profile_directory() -> Path:
        from quotapilot.capabilities.loader import default_profile_directory

        return default_profile_directory()
