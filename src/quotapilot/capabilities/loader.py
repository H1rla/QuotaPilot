"""Safe YAML loading for capability-profile documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from quotapilot.capabilities.errors import (
    ProfileLoadError,
    ProfileValidationError,
    UnsupportedProfileVersionError,
)
from quotapilot.capabilities.models import (
    SUPPORTED_PROFILE_SCHEMA_VERSION,
    ModelProfileDocument,
)


def load_profile(path: str | Path) -> ModelProfileDocument:
    """Load one profile with `safe_load`; arbitrary YAML objects are rejected."""
    profile_path = Path(path)
    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileLoadError(f"failed to read model profile {profile_path.name}") from exc

    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProfileLoadError(f"malformed YAML in model profile {profile_path.name}") from exc
    if not isinstance(raw, dict):
        raise ProfileValidationError(
            f"model profile {profile_path.name} must contain a top-level mapping"
        )

    version = raw.get("schema_version")
    if type(version) is int and version != SUPPORTED_PROFILE_SCHEMA_VERSION:
        raise UnsupportedProfileVersionError(
            f"unsupported profile schema version {version} in {profile_path.name}"
        )
    try:
        return ModelProfileDocument.model_validate(raw)
    except ValidationError as exc:
        raise ProfileValidationError(
            f"invalid model profile schema in {profile_path.name}"
        ) from exc


def default_profile_directory() -> Path:
    """Return the repository-shipped, Git-reviewable profile directory."""
    package_data = Path(__file__).resolve().parents[1] / "_data" / "model_profiles"
    if package_data.is_dir():
        return package_data
    return Path(__file__).resolve().parents[3] / "policies" / "model_profiles"
