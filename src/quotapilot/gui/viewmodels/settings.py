"""Strict common-policy settings editor."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import Property, Signal, Slot

from quotapilot.config import AppConfig, save_user_config
from quotapilot.execution.models import ExecutionMode

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from .base import BaseViewModel


def validate_settings_update(
    config: AppConfig,
    *,
    reserve_fraction: str,
    timezone: str,
    stale_after_seconds: str,
    unknown_quota_pressure: str,
    execution_mode: str,
    timeout_seconds: str,
    max_attempts: str,
    max_same_step_retries: str,
) -> AppConfig:
    """Parse human form values once, then run authoritative strict models."""
    raw = config.model_dump(mode="python")
    raw["budget"]["reserve_fraction"] = float(reserve_fraction)
    raw["budget"]["timezone"] = timezone.strip()
    raw["budget"]["stale_after_seconds"] = int(stale_after_seconds)
    raw["routing"]["unknown_quota_pressure"] = float(unknown_quota_pressure)
    raw["execution"]["mode"] = ExecutionMode(execution_mode)
    raw["execution"]["timeout_seconds"] = int(timeout_seconds)
    raw["execution"]["max_attempts"] = int(max_attempts)
    raw["execution"]["max_same_step_retries"] = int(max_same_step_retries)
    return AppConfig.model_validate(raw)


class SettingsViewModel(BaseViewModel):
    settingsChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self._config = dependencies.effective.config
        self._saved_message = ""

    @Property(dict, notify=settingsChanged)
    def data(self) -> dict[str, Any]:
        config = self._config
        return {
            "provider": config.provider.default or "openai-codex",
            "databasePath": config.database.path or "Platform default",
            "profileDirectory": config.profiles.directory or "Bundled profiles",
            "reserveFraction": str(config.budget.reserve_fraction),
            "timezone": config.budget.timezone,
            "staleAfterSeconds": str(config.budget.stale_after_seconds),
            "unknownQuotaPressure": str(config.routing.unknown_quota_pressure),
            "executionMode": config.execution.mode.value,
            "timeoutSeconds": str(config.execution.timeout_seconds),
            "maxAttempts": str(config.execution.max_attempts),
            "maxSameStepRetries": str(config.execution.max_same_step_retries),
            "configPath": str(self._dependencies.effective.path),
        }

    @Property(str, notify=settingsChanged)
    def savedMessage(self) -> str:  # noqa: N802
        return self._saved_message

    @Slot(str, str, str, str, str, str, str, str)
    def save(  # noqa: PLR0913 - mirrors the visible settings form
        self,
        reserve_fraction: str,
        timezone: str,
        stale_after_seconds: str,
        unknown_quota_pressure: str,
        execution_mode: str,
        timeout_seconds: str,
        max_attempts: str,
        max_same_step_retries: str,
    ) -> None:
        if self.busy:
            return
        try:
            candidate = validate_settings_update(
                self._config,
                reserve_fraction=reserve_fraction,
                timezone=timezone,
                stale_after_seconds=stale_after_seconds,
                unknown_quota_pressure=unknown_quota_pressure,
                execution_mode=execution_mode,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                max_same_step_retries=max_same_step_retries,
            )
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                location = ".".join(str(part) for part in exc.errors()[0]["loc"])
                message = exc.errors()[0]["msg"]
                self._fail(f"Invalid setting at {location}: {message}", "Review value")
            else:
                self._fail("Invalid setting value.", "Review value")
            self.settingsChanged.emit()
            return

        self._begin()
        self._saved_message = ""

        async def operation() -> AppConfig:
            save_user_config(candidate, path=self._dependencies.effective.path)
            return candidate

        def success(value: object) -> None:
            if isinstance(value, AppConfig):
                self._config = value
            self._saved_message = "Saved · changes apply on next launch"
            self._finish()
            self.settingsChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail("Configuration could not be saved.", "Retry")
            self.settingsChanged.emit()

        self._runner.start(operation, success, failure)
