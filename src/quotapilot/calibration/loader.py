"""Safe YAML loading for synthetic calibration scenarios."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from quotapilot.calibration.errors import (
    CalibrationLoadError,
    CalibrationValidationError,
)
from quotapilot.calibration.models import CalibrationSuite


def load_calibration_suite(path: str | Path) -> CalibrationSuite:
    suite_path = Path(path)
    try:
        text = suite_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CalibrationLoadError("failed to read calibration scenario data") from exc
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CalibrationLoadError("malformed calibration YAML") from exc
    if not isinstance(raw, dict):
        raise CalibrationValidationError("calibration data must be a top-level mapping")
    try:
        return CalibrationSuite.model_validate(raw)
    except ValidationError as exc:
        raise CalibrationValidationError("invalid calibration scenario schema") from exc


def default_calibration_path() -> Path:
    package_data = (
        Path(__file__).resolve().parents[1]
        / "_data"
        / "calibration"
        / "scenarios.yaml"
    )
    if package_data.is_file():
        return package_data
    return Path(__file__).resolve().parents[3] / "calibration" / "scenarios.yaml"
