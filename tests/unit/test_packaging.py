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


def test_gui_runtime_dependency_and_qml_assets_are_present() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    qml = ROOT / "src" / "quotapilot" / "gui" / "qml"

    assert any(
        dependency.startswith("pyside6")
        for dependency in metadata["project"]["dependencies"]
    )
    assert (qml / "Main.qml").is_file()
    assert (qml / "Tokens.js").is_file()
    assert (qml / "components" / "ForecastStrip.qml").is_file()
    assert not (qml / "components" / "UsageChart.qml").exists()
    assert {
        "Overview.qml",
        "Usage.qml",
        "Models.qml",
        "Route.qml",
        "Execute.qml",
        "History.qml",
        "Settings.qml",
    } <= {path.name for path in qml.glob("*.qml")}
    i18n = ROOT / "src" / "quotapilot" / "gui" / "i18n"
    assert {
        "quotapilot_en.ts",
        "quotapilot_en.qm",
        "quotapilot_ja.ts",
        "quotapilot_ja.qm",
    } <= {path.name for path in i18n.iterdir()}
    assert "<translation>概要</translation>" in (i18n / "quotapilot_ja.ts").read_text(
        encoding="utf-8"
    )


def test_tui_runtime_dependency_and_assets_are_present() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tui = ROOT / "src" / "quotapilot" / "tui"

    assert any(
        dependency.startswith("textual")
        for dependency in metadata["project"]["dependencies"]
    )
    assert (tui / "styles" / "quotapilot.tcss").is_file()
    assert (tui / "locales" / "en.yaml").is_file()
    assert (tui / "locales" / "ja.yaml").is_file()


def test_linux_desktop_entry_is_portable_and_included_in_sdist() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    desktop_entry = (
        ROOT / "packaging" / "linux" / "io.github.H1rla.QuotaPilot.desktop"
    )
    content = desktop_entry.read_text(encoding="utf-8")

    assert "/packaging" in metadata["tool"]["hatch"]["build"]["targets"]["sdist"][
        "include"
    ]
    assert "Type=Application" in content
    assert "Exec=quotapilot gui" in content
    assert "Terminal=false" in content
    assert "/home/" not in content
    assert "Icon=" not in content
