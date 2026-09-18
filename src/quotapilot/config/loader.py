"""Safe YAML loading and deterministic config-source precedence."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import platformdirs
import yaml
from pydantic import ValidationError

from quotapilot.config.errors import ConfigLoadError, ConfigValidationError
from quotapilot.config.models import AppConfig, LanguagePreference
from quotapilot.execution.models import ExecutionMode, FailureClass

_APP_NAME = "quotapilot"


def default_config_path() -> Path:
    """Return the platform-resolved canonical optional config path."""
    return Path(platformdirs.user_config_dir(_APP_NAME)) / "config.yaml"


@dataclass(frozen=True, slots=True)
class EffectiveConfig:
    """Validated policy plus the winning source for every leaf field."""

    config: AppConfig
    sources: dict[str, str]
    path: Path
    file_present: bool


def _parse_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigValidationError(f"environment variable {name} must be a number") from exc
    return parsed


def _parse_int(name: str, value: str) -> int:
    try:
        # Reject float-looking values instead of silently truncating them.
        return int(value)
    except ValueError as exc:
        raise ConfigValidationError(f"environment variable {name} must be an integer") from exc


def _parse_mode(name: str, value: str) -> ExecutionMode:
    try:
        return ExecutionMode(value)
    except ValueError as exc:
        raise ConfigValidationError(
            f"environment variable {name} has an invalid execution mode"
        ) from exc


def _identity(_name: str, value: str) -> str:
    return value


_ENVIRONMENT_FIELDS: dict[str, tuple[str, Callable[[str, str], Any]]] = {
    "QUOTAPILOT_PROVIDER": ("provider.default", _identity),
    "QUOTAPILOT_DATABASE_PATH": ("database.path", _identity),
    "QUOTAPILOT_PROFILE_DIR": ("profiles.directory", _identity),
    "QUOTAPILOT_BUDGET_RESERVE_FRACTION": ("budget.reserve_fraction", _parse_float),
    "QUOTAPILOT_BUDGET_TIMEZONE": ("budget.timezone", _identity),
    "QUOTAPILOT_BUDGET_STALE_AFTER_SECONDS": (
        "budget.stale_after_seconds",
        _parse_int,
    ),
    "QUOTAPILOT_ROUTING_UNKNOWN_QUOTA_PRESSURE": (
        "routing.unknown_quota_pressure",
        _parse_float,
    ),
    "QUOTAPILOT_EXECUTION_MODE": ("execution.mode", _parse_mode),
    "QUOTAPILOT_EXECUTION_MAX_ATTEMPTS": (
        "execution.max_attempts",
        _parse_int,
    ),
    "QUOTAPILOT_EXECUTION_MAX_SAME_STEP_RETRIES": (
        "execution.max_same_step_retries",
        _parse_int,
    ),
    "QUOTAPILOT_EXECUTION_TIMEOUT_SECONDS": (
        "execution.timeout_seconds",
        _parse_int,
    ),
}


def _nested_items(value: Mapping[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, Mapping):
            items.extend(_nested_items(item, path))
        else:
            items.append((path, item))
    return items


def _set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    current = target
    for key in keys[:-1]:
        nested = current.get(key)
        if not isinstance(nested, dict):
            nested = {}
            current[key] = nested
        current = nested
    current[keys[-1]] = value


def _normalize_file_value(dotted: str, value: Any) -> Any:
    """Convert only documented YAML representations at the loader boundary."""
    if dotted == "execution.mode" and isinstance(value, str):
        try:
            return ExecutionMode(value)
        except ValueError as exc:
            raise ConfigValidationError("invalid configuration at execution.mode") from exc
    if dotted == "appearance.language" and isinstance(value, str):
        try:
            return LanguagePreference(value)
        except ValueError as exc:
            raise ConfigValidationError("invalid configuration at appearance.language") from exc
    if dotted in {"execution.retryable_failures", "execution.escalation_failures"}:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            return value
        try:
            return tuple(FailureClass(item) for item in value)
        except ValueError as exc:
            raise ConfigValidationError(f"invalid configuration at {dotted}") from exc
    return value


def _merge_file_mapping(
    target: dict[str, Any],
    incoming: Mapping[str, Any],
    sources: dict[str, str],
    prefix: str = "",
) -> None:
    """Deep-merge while retaining unknown/empty keys for strict validation."""
    for key, value in incoming.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            existing = target.get(key)
            nested = existing if isinstance(existing, dict) else {}
            target[key] = nested
            if value:
                _merge_file_mapping(nested, value, sources, dotted)
            else:
                # Keeping an unknown empty mapping lets `extra=forbid` reject it.
                sources[dotted] = "user-config"
            continue
        target[key] = _normalize_file_value(dotted, value)
        sources[dotted] = "user-config"


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigLoadError(f"failed to read configuration file {path}") from exc
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"malformed YAML in configuration file {path}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigValidationError("configuration must contain a top-level mapping")
    return raw


def _default_sources(config: AppConfig) -> dict[str, str]:
    dumped = config.model_dump(mode="python")
    return {
        path: (
            "policy-default"
            if path.split(".", maxsplit=1)[0] in {"budget", "routing", "execution"}
            else "built-in-default"
        )
        for path, _value in _nested_items(dumped)
    }


def load_effective_config(
    *,
    path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> EffectiveConfig:
    """Load defaults < YAML < selected environment < explicit CLI values.

    Environment strings are parsed explicitly here so strict policy models
    never acquire implicit string-to-number coercion.
    """
    env = os.environ if environ is None else environ
    configured_path = path or env.get("QUOTAPILOT_CONFIG")
    config_path = Path(configured_path).expanduser() if configured_path else default_config_path()

    defaults = AppConfig()
    merged = deepcopy(defaults.model_dump(mode="python"))
    sources = _default_sources(defaults)

    file_present = config_path.is_file()
    if file_present:
        raw = _read_yaml(config_path)
        _merge_file_mapping(merged, raw, sources)

    for env_name, (dotted, parser) in _ENVIRONMENT_FIELDS.items():
        if env_name not in env:
            continue
        _set_path(merged, dotted, parser(env_name, env[env_name]))
        sources[dotted] = "environment"

    for dotted, value in (cli_overrides or {}).items():
        if value is None:
            continue
        _set_path(merged, dotted, value)
        sources[dotted] = "cli"

    try:
        config = AppConfig.model_validate(merged)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.errors()[0]["loc"])
        message = exc.errors()[0]["msg"]
        raise ConfigValidationError(f"invalid configuration at {location}: {message}") from exc

    # Fill any defaulted nested leaves absent from the raw source map.
    for dotted, _value in _nested_items(config.model_dump(mode="python")):
        sources.setdefault(
            dotted,
            "policy-default"
            if dotted.split(".", maxsplit=1)[0] in {"budget", "routing", "execution"}
            else "built-in-default",
        )
    return EffectiveConfig(
        config=config,
        sources=sources,
        path=config_path,
        file_present=file_present,
    )
