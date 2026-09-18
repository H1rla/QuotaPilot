"""Release packaging metadata and bundled runtime resource smoke checks."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

from quotapilot import __version__
from quotapilot.calibration import default_calibration_path, load_calibration_suite
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_package_version_has_one_metadata_source() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == version("quotapilot")
    assert metadata["project"]["version"] == __version__


def test_runtime_profiles_and_calibration_are_loadable() -> None:
    ModelProfileRegistry.from_directory(default_profile_directory())
    suite = load_calibration_suite(default_calibration_path())

    assert suite.scenarios


def test_wheel_configuration_includes_required_runtime_assets() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    included = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

    assert included["policies/model_profiles"] == "quotapilot/_data/model_profiles"
    assert included["calibration/scenarios.yaml"] == (
        "quotapilot/_data/calibration/scenarios.yaml"
    )
