"""Daily forecast math, evidence, policy and calendar boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.forecast import DailyForecastService, ForecastUnavailable
from quotapilot.budget.models import BudgetConfig, BudgetState
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.gui.mappers import map_daily_forecast

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)
START = datetime(2026, 9, 24, tzinfo=UTC)
RESET = datetime(2026, 10, 2, tzinfo=UTC)


def sample(
    at: datetime,
    used: float | None,
    *,
    start: datetime | None = START,
    reset: datetime | None = RESET,
    pool_id: str = "weekly",
) -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="test", account_id=None,
            capabilities=CapabilitySet(models=()), observed_at=at,
        ),
        quota_pools=(QuotaPool(
            id=pool_id, provider="test", kind="rolling", scope="account",
            used_fraction=used,
            starts_at=start, resets_at=reset,
        ),),
        quota_bindings=(),
        captured_at=at,
    )


def forecast(
    rows: tuple[UsageSnapshot, ...], *, now: datetime = NOW,
    config: BudgetConfig | None = None,
):
    return DailyForecastService(BudgetEngine(config)).calculate(rows, now=now)


def test_partial_day_projection_exact_values_and_expected_delta() -> None:
    result = forecast((sample(NOW, 0.40), sample(NOW - timedelta(hours=3), 0.37)))
    assert result.unavailable_reason is None
    assert result.observed_seconds == 10800
    assert result.daily_rate == pytest.approx(0.24)
    assert len(result.points) == 7
    assert [point.projected_used_fraction for point in result.points[:3]] == pytest.approx(
        [0.52, 0.76, 1.0]
    )
    assert result.points[0].expected_used_fraction == pytest.approx(0.225)
    assert result.points[0].delta_from_expected == pytest.approx(0.295)
    assert result.points[0].state is BudgetState.CRITICAL
    assert result.points[3].projected_used_fraction == pytest.approx(1.24)
    assert result.points[3].exceeds_raw_quota
    assert map_daily_forecast(result)[3]["projectedText"] == "124%"
    assert result.points[0].is_today
    assert not result.points[1].is_today


def test_short_horizon_stops_at_reset_and_partial_reset_day() -> None:
    reset = NOW + timedelta(days=2, hours=2)
    rows = (
        sample(NOW, 0.40, reset=reset),
        sample(NOW - timedelta(hours=3), 0.37, reset=reset),
    )
    result = forecast(rows)
    assert [point.date.isoformat() for point in result.points] == [
        "2026-09-25", "2026-09-26", "2026-09-27",
    ]
    assert result.points[-1].projected_used_fraction == pytest.approx(0.90)
    assert result.points[-1].ends_at_reset


def test_reset_at_local_midnight_does_not_create_reset_date_point() -> None:
    reset = datetime(2026, 9, 27, tzinfo=UTC)
    result = forecast((sample(NOW, 0.4, reset=reset),
                       sample(NOW - timedelta(hours=3), 0.37, reset=reset)))
    assert [point.date.day for point in result.points] == [25, 26]
    assert result.points[-1].ends_at_reset


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ((), ForecastUnavailable.NO_SNAPSHOTS),
        ((sample(NOW, .4),), ForecastUnavailable.INSUFFICIENT_EVIDENCE),
        ((sample(NOW, .4), sample(NOW, .3)), ForecastUnavailable.INSUFFICIENT_EVIDENCE),
        ((sample(NOW, .4), sample(NOW - timedelta(minutes=59), .3)),
         ForecastUnavailable.INSUFFICIENT_EVIDENCE),
        ((sample(NOW, None), sample(NOW - timedelta(hours=2), .3)),
         ForecastUnavailable.QUOTA_UNKNOWN),
        ((sample(NOW, .4, reset=None), sample(NOW - timedelta(hours=2), .3, reset=None)),
         ForecastUnavailable.RESET_UNKNOWN),
        ((sample(NOW, .4, start=None), sample(NOW - timedelta(hours=2), .3, start=None)),
         ForecastUnavailable.TIMING_UNKNOWN),
        ((sample(NOW, .4, start=RESET), sample(NOW - timedelta(hours=2), .3,
                                              start=RESET)),
         ForecastUnavailable.MALFORMED_TIMING),
        ((sample(NOW, .4, reset=NOW), sample(NOW - timedelta(hours=2), .3, reset=NOW)),
         ForecastUnavailable.RESET_PASSED),
        ((sample(NOW, .3), sample(NOW - timedelta(hours=2), .4)),
         ForecastUnavailable.INCOMPATIBLE_WINDOW),
        ((sample(NOW, .4), sample(NOW - timedelta(hours=2), .3,
                                  reset=RESET + timedelta(days=1))),
         ForecastUnavailable.INCOMPATIBLE_WINDOW),
    ],
)
def test_unavailable_evidence_and_timing(
    rows: tuple[UsageSnapshot, ...], reason: ForecastUnavailable
) -> None:
    result = forecast(rows)
    assert result.unavailable_reason is reason
    assert not result.points


def test_multiple_today_snapshots_use_full_observation_interval() -> None:
    rows = (sample(NOW, .4), sample(NOW - timedelta(hours=1), .39),
            sample(NOW - timedelta(hours=3), .37))
    result = forecast(rows)
    assert result.daily_rate == pytest.approx(.24)
    assert result.points[0].projected_used_fraction == pytest.approx(.52)


def test_configured_reserve_and_thresholds_drive_state() -> None:
    rows = (sample(NOW, .4), sample(NOW - timedelta(hours=3), .37))
    without_reserve = forecast(rows, config=BudgetConfig(reserve_fraction=0.0))
    with_reserve = forecast(rows, config=BudgetConfig(reserve_fraction=.5))
    assert with_reserve.points[0].expected_used_fraction == pytest.approx(.125)
    assert without_reserve.points[0].expected_used_fraction == pytest.approx(.25)
    assert (
        with_reserve.points[0].delta_from_expected
        > without_reserve.points[0].delta_from_expected
    )


def test_stale_persisted_and_provider_unavailable_need_no_live_call() -> None:
    rows = (sample(NOW - timedelta(hours=2), .38),
            sample(NOW - timedelta(hours=4), .36))
    result = forecast(rows)
    assert result.stale
    assert result.source == "persisted"
    assert result.points[0].projected_used_fraction == pytest.approx(.52)


def test_timezone_and_dst_use_actual_instants_for_observation() -> None:
    zone = ZoneInfo("America/New_York")
    now = datetime(2026, 3, 8, 12, tzinfo=zone)
    first = datetime(2026, 3, 8, 0, tzinfo=zone)
    reset = datetime(2026, 3, 10, 0, tzinfo=zone)
    start = datetime(2026, 3, 7, 0, tzinfo=zone)
    result = forecast(
        (sample(now, .4, start=start, reset=reset),
         sample(first, .29, start=start, reset=reset)),
        now=now, config=BudgetConfig(timezone="America/New_York"),
    )
    assert result.observed_seconds == 11 * 3600
    assert result.daily_rate == pytest.approx(.23)
    assert result.points[0].projected_used_fraction == pytest.approx(.52)
    assert [point.date.day for point in result.points] == [8, 9]


def test_same_inputs_and_now_produce_identical_immutable_result() -> None:
    rows = (sample(NOW, .4), sample(NOW - timedelta(hours=3), .37))
    service = DailyForecastService(BudgetEngine())
    assert service.calculate(rows, now=NOW) == service.calculate(rows, now=NOW)
