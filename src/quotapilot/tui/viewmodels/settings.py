"""Strict staged configuration editor over the canonical AppConfig and writer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from quotapilot.config import AppConfig, save_user_config
from quotapilot.config.loader import EffectiveConfig


@dataclass(frozen=True, slots=True)
class SettingSpec:
    key: str
    category: str
    kind: Literal["enum", "bool", "float", "int", "text"]
    options: tuple[str, ...] = ()


SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec("provider.default", "general", "enum", ("", "openai-codex")),
    SettingSpec("budget.reserve_fraction", "budget", "float"),
    SettingSpec("budget.timezone", "budget", "text"),
    SettingSpec("budget.stale_after_seconds", "budget", "int"),
    SettingSpec("routing.unknown_quota_pressure", "routing", "float"),
    SettingSpec("routing.escalation_enabled", "routing", "bool"),
    SettingSpec(
        "execution.mode",
        "execution",
        "enum",
        ("never_execute", "always_confirm", "confirm_on_escalation", "auto_for_low_risk"),
    ),
    SettingSpec("execution.timeout_seconds", "execution", "int"),
    SettingSpec("execution.max_attempts", "execution", "int"),
    SettingSpec("execution.max_same_step_retries", "execution", "int"),
    SettingSpec("execution.require_fresh_budget", "execution", "bool"),
    SettingSpec("execution.allow_escalation", "execution", "bool"),
    SettingSpec("profiles.directory", "models_profiles", "text"),
    SettingSpec("database.path", "integration", "text"),
    SettingSpec("appearance.language", "appearance", "enum", ("system", "en", "ja")),
    SettingSpec("appearance.tui_theme", "appearance", "enum", ("system", "dark", "light")),
)
CATEGORIES = (
    "general",
    "budget",
    "routing",
    "execution",
    "models_profiles",
    "integration",
    "appearance",
)


def setting_value(config: AppConfig, key: str) -> str:
    section, name = key.split(".")
    value = getattr(getattr(config, section), name)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def validate_update(config: AppConfig, spec: SettingSpec, value: str) -> AppConfig:
    """Parse only the selected human control, then use strict policy validation."""
    if spec.kind == "enum":
        if value not in spec.options:
            raise ValueError("choose one of the listed values")
        parsed: object = None if value == "" else value
        current = getattr(getattr(config, spec.key.split(".")[0]), spec.key.split(".")[1])
        if isinstance(current, Enum) and parsed is not None:
            parsed = type(current)(parsed)
    elif spec.kind == "bool":
        if value not in {"true", "false"}:
            raise ValueError("choose true or false")
        parsed = value == "true"
    elif spec.kind == "float":
        parsed = float(value)
    elif spec.kind == "int":
        if value.strip() != value:
            raise ValueError("enter an integer")
        parsed = int(value)
    else:
        parsed = (
            value.strip() or None
            if spec.key in {"profiles.directory", "database.path"}
            else value.strip()
        )
    section, name = spec.key.split(".")
    raw = config.model_dump(mode="python")
    raw[section][name] = parsed
    return AppConfig.model_validate(raw)


class SettingsViewModel:
    def __init__(self, effective: EffectiveConfig) -> None:
        self.path: Path = effective.path
        self.saved = effective.config
        self.draft = effective.config
        self.active = False
        self.error: str | None = None

    @property
    def dirty(self) -> bool:
        return self.draft != self.saved

    def update(self, spec: SettingSpec, value: str) -> bool:
        try:
            self.draft = validate_update(self.draft, spec, value)
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                first = exc.errors()[0]
                location = ".".join(str(part) for part in first["loc"])
                self.error = f"{location}: {first['msg']}"
            else:
                self.error = str(exc)
            return False
        self.error = None
        return True

    async def save(self) -> bool:
        if self.active or not self.dirty:
            return False
        self.active = True
        candidate = self.draft
        try:
            await asyncio.to_thread(save_user_config, candidate, path=self.path)
        except Exception:  # noqa: BLE001 - no raw filesystem error in UI
            self.error = "settings.save_error"
            return False
        finally:
            self.active = False
        self.saved = candidate
        self.error = None
        return True

    def discard(self) -> None:
        self.draft = self.saved
        self.error = None
