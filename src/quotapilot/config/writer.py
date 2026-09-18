"""Validated, atomic persistence for the central user configuration."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from quotapilot.config.errors import ConfigLoadError
from quotapilot.config.loader import default_config_path
from quotapilot.config.models import AppConfig


def save_user_config(config: AppConfig, *, path: str | Path | None = None) -> Path:
    """Write one already-validated config without exposing process environment.

    A sibling temporary file plus ``os.replace`` keeps the prior configuration
    intact if serialization or writing fails.
    """
    target = Path(path).expanduser() if path is not None else default_config_path()
    payload: dict[str, Any] = config.model_dump(mode="json")
    try:
        encoded = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"failed to write configuration file {target}") from exc
    return target
