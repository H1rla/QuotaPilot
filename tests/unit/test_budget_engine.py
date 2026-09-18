"""Deterministic, provider-independent Budget Engine tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.errors import BudgetEvaluationError
from quotapilot.budget.models import (
    BudgetConfig,
    BudgetState,
    RemainingSource,
    TimingSource,
    WeekdayWeights,
)
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot

MONDAY_NOON = datetime(2026, 9, 14, 12, tzinfo=UTC)


def _pool(
    pool_id: str = "weekly",
    *,
    used: float | None = 0.5,
    remaining: float | None = 0.5,
    start: datetime | None = None,
    reset: datetime | None = None,
    window_seconds: int | None = None,
) -> QuotaPool:
    return QuotaPool(
        id=pool_id,
        provider="test-provider",
        kind="unknown",
        scope="unknown",
        used_fraction=used,
        remaining_fraction=remaining,
        starts_at=start,
        resets_at=reset,
        window_seconds=window_seconds,
        raw_name=pool_id.title(),
    )


def _snapshot(
    *pools: QuotaPool,
    captured_at: datetime = MONDAY_NOON,
) -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="test-provider",
            capabilities=CapabilitySet(models=()),
            observed_at=captured_at,
        ),
        quota_pools=pools,
        quota_bindings=(),
        captured_at=captured_at,
    )


def _assess(
    pool: QuotaPool,
    *,
    now: datetime = MONDAY_NOON,
    config: BudgetConfig | None = None,
):
    return BudgetEngine(config).evaluate(_snapshot(pool, captured_at=now), now=now).pools[0]


def test_beginning_of_window_has_zero_expected_usage() -> None:
    assessment = _assess(
        _pool(
            used=0.0,
            remaining=1.0,
            start=MONDAY_NOON,
            reset=MONDAY_NOON + timedelta(days=7),
        )
    )

    assert assessment.window_progress == 0.0
    assert assessment.expected_usage == 0.0
    assert assessment.pace_delta == 0.0
    assert assessment.state is BudgetState.ON_TRACK


def test_midpoint_uses_reserve_aware_expected_usage() -> None:
    assessment = _assess(
        _pool(
            used=0.45,
            remaining=0.55,
            start=MONDAY_NOON - timedelta(days=5),
            reset=MONDAY_NOON + timedelta(days=5),
        )
    )

    assert assessment.window_progress == pytest.approx(0.5)
    assert assessment.expected_usage == pytest.approx(0.45)
    assert assessment.pace_delta == pytest.approx(0.0)


def test_near_reset_with_substantial_remaining_is_underused() -> None:
    assessment = _assess(
        _pool(
            used=0.60,
            remaining=0.40,
            start=MONDAY_NOON - timedelta(hours=90),
            reset=MONDAY_NOON + timedelta(hours=10),
        )
    )

    assert assessment.expected_usage == pytest.approx(0.81)
    assert assessment.pace_delta == pytest.approx(-0.21)
    assert assessment.state is BudgetState.VERY_UNDER
    assert assessment.pressure == 0.0


def test_after_reset_clamps_progress_and_has_no_daily_budget() -> None:
    assessment = _assess(
        _pool(
            used=0.8,
            remaining=0.2,
            start=MONDAY_NOON - timedelta(days=2),
            reset=MONDAY_NOON - timedelta(days=1),
        )
    )

    assert assessment.window_progress == 1.0
    assert assessment.expected_usage == 0.9
    assert assessment.time_until_reset_seconds == 0
    assert assessment.today_budget_fraction == 0.0
    assert "reset_time_passed" in assessment.warnings


def test_before_start_clamps_progress_but_does_not_allocate_today() -> None:
    assessment = _assess(
        _pool(
            used=0.0,
            remaining=1.0,
            start=MONDAY_NOON + timedelta(days=1),
            reset=MONDAY_NOON + timedelta(days=8),
        )
    )

    assert assessment.window_progress == 0.0
    assert assessment.expected_usage == 0.0
    assert assessment.today_budget_fraction is None
    assert "evaluation_before_window_start" in assessment.warnings


def test_zero_length_window_is_unknown() -> None:
    assessment = _assess(
        _pool(start=MONDAY_NOON, reset=MONDAY_NOON)
    )

    assert assessment.window_progress is None
    assert assessment.expected_usage is None
    assert assessment.pace_delta is None
    assert assessment.state is BudgetState.UNKNOWN
    assert "invalid_window_timing" in assessment.warnings


@pytest.mark.parametrize(
    ("start", "reset", "expected_daily"),
    [
        (None, MONDAY_NOON + timedelta(days=2), 0.4 / 3),
        (MONDAY_NOON - timedelta(days=1), None, None),
        (None, None, None),
    ],
)
def test_missing_timing_never_fabricates_pace(
    start: datetime | None,
    reset: datetime | None,
    expected_daily: float | None,
) -> None:
    assessment = _assess(
        _pool(used=0.5, remaining=0.5, start=start, reset=reset)
    )

    assert assessment.expected_usage is None
    assert assessment.pace_delta is None
    assert assessment.state is BudgetState.UNKNOWN
    if expected_daily is None:
        assert assessment.today_budget_fraction is None
    else:
        assert assessment.today_budget_fraction == pytest.approx(expected_daily)


def test_reset_and_window_seconds_derive_start_with_provenance() -> None:
    assessment = _assess(
        _pool(
            used=0.45,
            remaining=0.55,
            reset=MONDAY_NOON + timedelta(hours=5),
            window_seconds=10 * 60 * 60,
        )
    )

    assert assessment.timing_source is TimingSource.DERIVED_WINDOW_SECONDS
    assert assessment.window_progress == pytest.approx(0.5)
    assert assessment.expected_usage == pytest.approx(0.45)


def test_zero_window_seconds_cannot_derive_start() -> None:
    assessment = _assess(
        _pool(reset=MONDAY_NOON + timedelta(hours=5), window_seconds=0)
    )

    assert assessment.timing_source is None
    assert assessment.state is BudgetState.UNKNOWN
    assert "invalid_window_timing" in assessment.warnings


@pytest.mark.parametrize(
    ("reserve", "expected", "available"),
    [
        (0.0, 0.5, 0.5),
        (0.1, 0.45, 0.4),
        (0.99, 0.005, 0.0),
    ],
)
def test_reserve_policy_boundaries(reserve: float, expected: float, available: float) -> None:
    assessment = _assess(
        _pool(
            used=0.5,
            remaining=0.5,
            start=MONDAY_NOON - timedelta(days=1),
            reset=MONDAY_NOON + timedelta(days=1),
        ),
        config=BudgetConfig(reserve_fraction=reserve),
    )

    assert assessment.expected_usage == pytest.approx(expected)
    assert assessment.available_fraction == pytest.approx(available)


@pytest.mark.parametrize("reserve", [1.0, 1.1, -0.01])
def test_invalid_reserve_is_rejected(reserve: float) -> None:
    with pytest.raises(ValidationError):
        BudgetConfig(reserve_fraction=reserve)


@pytest.mark.parametrize(
    ("delta", "expected_state"),
    [
        (-0.201, BudgetState.VERY_UNDER),
        (-0.20, BudgetState.UNDER),
        (-0.071, BudgetState.UNDER),
        (-0.07, BudgetState.ON_TRACK),
        (0.07, BudgetState.ON_TRACK),
        (0.071, BudgetState.OVER),
        (0.20, BudgetState.OVER),
        (0.201, BudgetState.CRITICAL),
    ],
)
def test_state_threshold_boundaries(delta: float, expected_state: BudgetState) -> None:
    assessment = _assess(
        _pool(
            used=0.5 + delta,
            remaining=0.5 - delta,
            start=MONDAY_NOON - timedelta(days=1),
            reset=MONDAY_NOON + timedelta(days=1),
        ),
        config=BudgetConfig(reserve_fraction=0.0),
    )

    assert assessment.pace_delta == pytest.approx(delta)
    assert assessment.state is expected_state


def test_equal_weekday_weights_allocate_across_inclusive_remaining_dates() -> None:
    assessment = _assess(
        _pool(used=0.5, remaining=0.5, reset=MONDAY_NOON + timedelta(days=3))
    )

    assert assessment.today_budget_fraction == pytest.approx(0.4 / 4)


def test_unequal_weekday_weights_are_applied() -> None:
    weights = WeekdayWeights(monday=2.0, tuesday=1.0, wednesday=1.0)
    assessment = _assess(
        _pool(used=0.5, remaining=0.5, reset=MONDAY_NOON + timedelta(days=2)),
        config=BudgetConfig(weekday_weights=weights),
    )

    assert assessment.today_budget_fraction == pytest.approx(0.4 * 2 / 4)


def test_final_partial_day_receives_all_available_quota() -> None:
    assessment = _assess(
        _pool(used=0.5, remaining=0.5, reset=MONDAY_NOON + timedelta(hours=10))
    )

    assert assessment.today_budget_fraction == pytest.approx(0.4)


def test_reset_at_midnight_excludes_reset_day() -> None:
    reset = datetime(2026, 9, 16, 0, 0, tzinfo=UTC)
    assessment = _assess(_pool(used=0.5, remaining=0.5, reset=reset))

    assert assessment.today_budget_fraction == pytest.approx(0.4 / 2)


def test_daily_allocation_uses_configured_timezone_calendar() -> None:
    now = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)  # Monday 23:00 in Tokyo
    reset = datetime(2026, 9, 15, 16, 0, tzinfo=UTC)  # Wednesday 01:00 in Tokyo
    assessment = _assess(
        _pool(used=0.5, remaining=0.5, reset=reset),
        now=now,
        config=BudgetConfig(timezone="Asia/Tokyo"),
    )

    assert assessment.today_budget_fraction == pytest.approx(0.4 / 3)


def test_zero_available_quota_has_zero_daily_budget() -> None:
    assessment = _assess(
        _pool(used=0.95, remaining=0.05, reset=MONDAY_NOON + timedelta(days=3))
    )

    assert assessment.available_fraction == 0.0
    assert assessment.today_budget_fraction == 0.0


def test_zero_weights_for_all_remaining_days_make_daily_budget_unknown() -> None:
    saturday = datetime(2026, 9, 19, 12, tzinfo=UTC)
    weights = WeekdayWeights(saturday=0.0, sunday=0.0)
    assessment = _assess(
        _pool(reset=saturday + timedelta(days=1)),
        now=saturday,
        config=BudgetConfig(weekday_weights=weights),
    )

    assert assessment.today_budget_fraction is None
    assert "remaining_day_weights_zero" in assessment.warnings


def _paced_pool(pool_id: str, delta: float, *, remaining: float | None = None) -> QuotaPool:
    used = 0.5 + delta
    return _pool(
        pool_id,
        used=used,
        remaining=(1.0 - used) if remaining is None else remaining,
        start=MONDAY_NOON - timedelta(days=1),
        reset=MONDAY_NOON + timedelta(days=1),
    )


def test_weekly_critical_binds_when_short_window_is_safe() -> None:
    report = BudgetEngine(BudgetConfig(reserve_fraction=0.0)).evaluate(
        _snapshot(_paced_pool("5h", -0.1), _paced_pool("weekly", 0.3)),
        now=MONDAY_NOON,
    )

    assert report.binding_pool_id == "weekly"
    assert report.effective_pressure == 1.0


def test_short_window_critical_binds_when_weekly_is_safe() -> None:
    report = BudgetEngine(BudgetConfig(reserve_fraction=0.0)).evaluate(
        _snapshot(_paced_pool("5h", 0.3), _paced_pool("weekly", -0.1)),
        now=MONDAY_NOON,
    )

    assert report.binding_pool_id == "5h"


def test_unknown_pool_does_not_override_known_pressure() -> None:
    report = BudgetEngine(BudgetConfig(reserve_fraction=0.0)).evaluate(
        _snapshot(_pool("unknown", used=0.9, remaining=0.1), _paced_pool("known", 0.08)),
        now=MONDAY_NOON,
    )

    assert report.pools[0].state is BudgetState.UNKNOWN
    assert report.pools[0].pressure is None
    assert report.binding_pool_id == "known"
    assert report.effective_pressure == 0.70


def test_binding_tie_uses_remaining_then_pool_id() -> None:
    report = BudgetEngine(BudgetConfig(reserve_fraction=0.0)).evaluate(
        _snapshot(
            _paced_pool("z-pool", 0.1, remaining=0.4),
            _paced_pool("b-pool", 0.1, remaining=0.3),
            _paced_pool("a-pool", 0.1, remaining=0.3),
        ),
        now=MONDAY_NOON,
    )

    assert report.binding_pool_id == "a-pool"


def test_no_evaluable_pool_has_no_effective_pressure() -> None:
    report = BudgetEngine().evaluate(_snapshot(_pool()), now=MONDAY_NOON)

    assert report.effective_pressure is None
    assert report.binding_pool_id is None


def test_fresh_stale_and_future_snapshot_age_behavior() -> None:
    engine = BudgetEngine(BudgetConfig(stale_after_seconds=60))
    pool = _pool()

    fresh = engine.evaluate(
        _snapshot(pool, captured_at=MONDAY_NOON - timedelta(seconds=60)),
        now=MONDAY_NOON,
    )
    stale = engine.evaluate(
        _snapshot(pool, captured_at=MONDAY_NOON - timedelta(seconds=61)),
        now=MONDAY_NOON,
    )
    future = engine.evaluate(
        _snapshot(pool, captured_at=MONDAY_NOON + timedelta(seconds=1)),
        now=MONDAY_NOON,
    )

    assert fresh.is_stale is False
    assert stale.is_stale is True
    assert "snapshot_stale" in stale.warnings
    assert future.is_stale is False
    assert future.snapshot_age_seconds == -1
    assert "snapshot_captured_in_future" in future.warnings


def test_same_inputs_always_produce_equal_report() -> None:
    snapshot = _snapshot(
        _paced_pool("5h", 0.08),
        _paced_pool("weekly", -0.1),
    )
    engine = BudgetEngine()

    assert engine.evaluate(snapshot, now=MONDAY_NOON) == engine.evaluate(
        snapshot, now=MONDAY_NOON
    )


def test_report_fraction_invariants() -> None:
    assessment = _assess(
        _pool(
            used=0.6,
            remaining=None,
            start=MONDAY_NOON - timedelta(days=2),
            reset=MONDAY_NOON + timedelta(days=3),
        )
    )

    assert assessment.remaining_source is RemainingSource.DERIVED_USED_FRACTION
    for value in (
        assessment.actual_usage,
        assessment.expected_usage,
        assessment.remaining_fraction,
        assessment.available_fraction,
        assessment.today_budget_fraction,
        assessment.window_progress,
        assessment.pressure,
    ):
        assert value is None or 0.0 <= value <= 1.0
    assert assessment.today_budget_fraction is not None
    assert assessment.available_fraction is not None
    assert assessment.today_budget_fraction <= assessment.available_fraction


def test_report_warns_on_inconsistent_used_and_remaining() -> None:
    assessment = _assess(
        _pool(
            used=0.2,
            remaining=0.2,
            start=MONDAY_NOON - timedelta(days=1),
            reset=MONDAY_NOON + timedelta(days=1),
        )
    )

    assert assessment.remaining_source is RemainingSource.REPORTED
    assert "used_remaining_inconsistent" in assessment.warnings


def test_missing_actual_usage_keeps_state_unknown_but_expected_is_available() -> None:
    assessment = _assess(
        _pool(
            used=None,
            remaining=0.8,
            start=MONDAY_NOON - timedelta(days=1),
            reset=MONDAY_NOON + timedelta(days=1),
        )
    )

    assert assessment.expected_usage == pytest.approx(0.45)
    assert assessment.pace_delta is None
    assert assessment.state is BudgetState.UNKNOWN


def test_invalid_config_order_timezone_weights_and_pressures_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BudgetConfig(under_threshold=-0.3)
    with pytest.raises(ValidationError):
        BudgetConfig(timezone="Not/A_Real_Zone")
    with pytest.raises(ValidationError):
        WeekdayWeights(
            monday=0,
            tuesday=0,
            wednesday=0,
            thursday=0,
            friday=0,
            saturday=0,
            sunday=0,
        )
    with pytest.raises(ValidationError):
        BudgetConfig(under_pressure=0.8, on_track_pressure=0.2)
    with pytest.raises(ValidationError):
        BudgetConfig(over_threshold=float("nan"))
    with pytest.raises(ValidationError):
        WeekdayWeights(monday=float("inf"))


def test_naive_evaluation_time_is_rejected() -> None:
    with pytest.raises(BudgetEvaluationError, match="timezone-aware"):
        BudgetEngine().evaluate(_snapshot(_pool()), now=datetime(2026, 9, 14, 12))


def test_duplicate_pool_ids_are_rejected() -> None:
    duplicate = _pool("duplicate")
    with pytest.raises(BudgetEvaluationError, match="unique"):
        BudgetEngine().evaluate(_snapshot(duplicate, duplicate), now=MONDAY_NOON)
