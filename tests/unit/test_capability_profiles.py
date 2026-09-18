"""Strict safe-loading, versioning, freshness, and exact registry tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from quotapilot.capabilities.errors import (
    AmbiguousProfileError,
    ProfileLoadError,
    ProfileValidationError,
    UnsupportedProfileVersionError,
)
from quotapilot.capabilities.loader import load_profile
from quotapilot.capabilities.models import (
    ProfileFreshness,
    ProvenanceSource,
)
from quotapilot.capabilities.registry import ModelProfileRegistry


def _profile_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": "test-provider",
        "product": "test-product",
        "verified_at": date(2026, 9, 18),
        "expires_after_days": 30,
        "models": {
            "exact-model": {
                "relative_power": 0.7,
                "relative_cost": 0.4,
                "relative_latency": 0.3,
                "effort_order": ["small", "large"],
                "provenance": {
                    "source": "manual",
                    "confidence": "provisional",
                    "evidence": ["Synthetic public evidence."],
                },
            }
        },
    }


def _write_yaml(path: Path, data: object) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_valid_profile_loads_with_typed_provenance(tmp_path: Path) -> None:
    profile = load_profile(_write_yaml(tmp_path / "valid.yaml", _profile_data()))

    assert profile.schema_version == 1
    assert profile.models["exact-model"].relative_power == 0.7
    assert (
        profile.models["exact-model"].provenance.source
        is ProvenanceSource.MANUAL
    )


def test_malformed_and_unsafe_yaml_fail_without_object_construction(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("models: [", encoding="utf-8")
    unsafe = tmp_path / "unsafe.yaml"
    unsafe.write_text("!!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")

    with pytest.raises(ProfileLoadError, match="malformed YAML"):
        load_profile(malformed)
    with pytest.raises(ProfileLoadError, match="malformed YAML"):
        load_profile(unsafe)


def test_unsupported_schema_version_is_typed(tmp_path: Path) -> None:
    data = _profile_data()
    data["schema_version"] = 2

    with pytest.raises(UnsupportedProfileVersionError):
        load_profile(_write_yaml(tmp_path / "future.yaml", data))


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("top_unknown", True),
        ("metric_low", -0.01),
        ("metric_high", 1.01),
        ("metric_string", "0.7"),
        ("metric_bool", True),
        ("missing_provenance", None),
        ("invalid_confidence", "certain"),
        ("invalid_verified_at", "not-a-date"),
        ("missing_verified_at", None),
    ],
)
def test_strict_profile_validation_rejects_bad_input(
    tmp_path: Path, mutation: str, value: object
) -> None:
    data = _profile_data()
    model = data["models"]["exact-model"]  # type: ignore[index]
    if mutation == "top_unknown":
        data["unexpected"] = value
    elif mutation.startswith("metric_"):
        model["relative_power"] = value  # type: ignore[index]
    elif mutation == "missing_provenance":
        del model["provenance"]  # type: ignore[attr-defined]
    elif mutation == "invalid_confidence":
        model["provenance"]["confidence"] = value  # type: ignore[index]
    elif mutation == "invalid_verified_at":
        data["verified_at"] = value
    elif mutation == "missing_verified_at":
        del data["verified_at"]

    with pytest.raises(ProfileValidationError):
        load_profile(_write_yaml(tmp_path / f"{mutation}.yaml", data))


def test_unknown_nested_keys_are_rejected(tmp_path: Path) -> None:
    data = _profile_data()
    data["models"]["exact-model"]["mystery"] = 1  # type: ignore[index]

    with pytest.raises(ProfileValidationError):
        load_profile(_write_yaml(tmp_path / "unknown.yaml", data))


def test_fresh_stale_future_and_no_expiry_states(tmp_path: Path) -> None:
    data = _profile_data()
    path = _write_yaml(tmp_path / "freshness.yaml", data)
    profile = load_profile(path)

    assert profile.freshness(date(2026, 9, 18)) is ProfileFreshness.FRESH
    assert profile.freshness(date(2026, 10, 19)) is ProfileFreshness.STALE
    assert profile.freshness(date(2026, 9, 17)) is ProfileFreshness.UNKNOWN

    data["expires_after_days"] = None
    no_expiry = load_profile(_write_yaml(tmp_path / "unknown-freshness.yaml", data))
    assert no_expiry.freshness(date(2026, 9, 18)) is ProfileFreshness.UNKNOWN


def test_registry_matches_exact_id_only(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "profile.yaml", _profile_data())
    registry = ModelProfileRegistry.from_directory(tmp_path)

    exact = registry.matches(
        "test-provider", "exact-model", evaluated_on=date(2026, 9, 18)
    )

    assert len(exact) == 1
    assert registry.matches(
        "test-provider", "exact-model-next", evaluated_on=date(2026, 9, 18)
    ) == ()
    assert registry.matches(
        "other-provider", "exact-model", evaluated_on=date(2026, 9, 18)
    ) == ()


def test_registry_uses_source_precedence_and_rejects_ambiguity(tmp_path: Path) -> None:
    manual = _profile_data()
    empirical = _profile_data()
    empirical["models"]["exact-model"]["provenance"]["source"] = "empirical"  # type: ignore[index]
    _write_yaml(tmp_path / "manual.yaml", manual)
    _write_yaml(tmp_path / "empirical.yaml", empirical)
    registry = ModelProfileRegistry.from_directory(tmp_path)

    matches = registry.matches(
        "test-provider", "exact-model", evaluated_on=date(2026, 9, 18)
    )

    assert [match.profile.provenance.source for match in matches] == [
        ProvenanceSource.EMPIRICAL,
        ProvenanceSource.MANUAL,
    ]

    _write_yaml(tmp_path / "manual-duplicate.yaml", manual)
    with pytest.raises(AmbiguousProfileError):
        ModelProfileRegistry.from_directory(tmp_path)
