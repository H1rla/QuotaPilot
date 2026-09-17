from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from quotapilot.domain.quota import QuotaBinding, QuotaPool


def _now() -> datetime:
    return datetime.now(UTC)


def test_quota_pool_accepts_valid_fractions() -> None:
    pool = QuotaPool(
        id="weekly",
        provider="openai-codex",
        kind="rolling",
        scope="account",
        used_fraction=0.65,
        remaining_fraction=0.35,
        starts_at=_now() - timedelta(days=3),
        resets_at=_now() + timedelta(days=4),
        window_seconds=7 * 24 * 3600,
    )

    assert pool.used_fraction == 0.65
    assert pool.remaining_fraction == 0.35


def test_quota_pool_allows_missing_fractions() -> None:
    pool = QuotaPool(id="unknown-pool", provider="openai-codex", kind="unknown", scope="unknown")

    assert pool.used_fraction is None
    assert pool.remaining_fraction is None


@pytest.mark.parametrize("fraction", [-0.01, 1.01, 2.0])
def test_quota_pool_rejects_out_of_range_fraction(fraction: float) -> None:
    with pytest.raises(ValidationError):
        QuotaPool(
            id="weekly",
            provider="openai-codex",
            kind="rolling",
            scope="account",
            used_fraction=fraction,
        )


def test_quota_pool_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        QuotaPool(
            id="weekly",
            provider="openai-codex",
            kind="rolling",
            scope="account",
            resets_at=datetime.now(),  # noqa: DTZ005 - intentionally naive for the test
        )


def test_quota_pool_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        QuotaPool(id="weekly", provider="openai-codex", kind="bogus", scope="account")  # type: ignore[arg-type]


def test_applies_to_models_is_an_immutable_tuple() -> None:
    pool = QuotaPool(
        id="weekly",
        provider="openai-codex",
        kind="unknown",
        scope="unknown",
        applies_to_models=("model-a",),
    )

    assert isinstance(pool.applies_to_models, tuple)
    with pytest.raises(AttributeError):
        pool.applies_to_models.append("model-b")  # type: ignore[attr-defined]


def test_quota_binding_is_many_to_many() -> None:
    binding = QuotaBinding(
        model_id="gpt-5-codex",
        reasoning_effort="high",
        quota_pool_ids=("five-hour", "weekly"),
        confidence="observed",
    )

    assert binding.quota_pool_ids == ("five-hour", "weekly")
