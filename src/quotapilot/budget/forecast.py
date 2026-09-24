"""Deterministic daily quota projection from persisted normalized observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import BudgetState
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot

MIN_OBSERVATION_SECONDS = 3600
MAX_POINTS = 7


class ForecastUnavailable(StrEnum):
    NO_SNAPSHOTS = "no_snapshots"
    QUOTA_UNKNOWN = "quota_unknown"
    RESET_UNKNOWN = "reset_unknown"
    TIMING_UNKNOWN = "timing_unknown"
    RESET_PASSED = "reset_passed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCOMPATIBLE_WINDOW = "incompatible_window"
    MALFORMED_TIMING = "malformed_timing"


@dataclass(frozen=True, slots=True)
class DailyForecastPoint:
    date: date
    is_today: bool
    projected_used_fraction: float
    projected_remaining_fraction: float
    expected_used_fraction: float
    delta_from_expected: float
    state: BudgetState
    exceeds_raw_quota: bool
    ends_at_reset: bool


@dataclass(frozen=True, slots=True)
class DailyForecast:
    generated_at: datetime
    basis: str
    source: str
    stale: bool
    points: tuple[DailyForecastPoint, ...] = ()
    unavailable_reason: ForecastUnavailable | None = None
    observed_seconds: float | None = None
    daily_rate: float | None = None


class DailyForecastService:
    """Project the selected pool using same-day observations and BudgetEngine policy."""

    def __init__(self, budget: BudgetEngine) -> None:
        self._budget = budget

    def calculate(self, snapshots: tuple[UsageSnapshot, ...], *, now: datetime) -> DailyForecast:
        if now.utcoffset() is None:
            raise ValueError("forecast time must be timezone-aware")
        now_utc = now.astimezone(UTC)
        zone = ZoneInfo(self._budget.config.timezone)
        result = DailyForecast(now, "today_observed_pace", "persisted", False)
        if not snapshots:
            return self._unavailable(result, ForecastUnavailable.NO_SNAPSHOTS)

        ordered = sorted(snapshots, key=lambda item: item.captured_at.astimezone(UTC))
        latest = ordered[-1]
        report = self._budget.evaluate(latest, now=now)
        result = DailyForecast(now, "today_observed_pace", "persisted", report.is_stale)
        assessment = next(
            (pool for pool in report.pools if pool.pool_id == report.binding_pool_id),
            report.pools[0] if report.pools else None,
        )
        if assessment is None or assessment.actual_usage is None:
            return self._unavailable(result, ForecastUnavailable.QUOTA_UNKNOWN)
        pool = next(pool for pool in latest.quota_pools if pool.id == assessment.pool_id)
        if pool.resets_at is None:
            return self._unavailable(result, ForecastUnavailable.RESET_UNKNOWN)
        reset = pool.resets_at.astimezone(UTC)
        if reset <= now_utc:
            return self._unavailable(result, ForecastUnavailable.RESET_PASSED)
        bounds = self._budget.window_bounds(pool)
        if bounds is None:
            reason = (
                ForecastUnavailable.MALFORMED_TIMING
                if "invalid_window_timing" in assessment.warnings
                else ForecastUnavailable.TIMING_UNKNOWN
            )
            return self._unavailable(result, reason)
        if assessment.expected_usage is None or assessment.state is BudgetState.UNKNOWN:
            return self._unavailable(result, ForecastUnavailable.TIMING_UNKNOWN)
        if now_utc < bounds[0]:
            return self._unavailable(result, ForecastUnavailable.MALFORMED_TIMING)
        if latest.captured_at.astimezone(UTC) > now_utc:
            return self._unavailable(result, ForecastUnavailable.MALFORMED_TIMING)

        today = now_utc.astimezone(zone).date()
        if latest.captured_at.astimezone(zone).date() != today:
            return self._unavailable(result, ForecastUnavailable.INSUFFICIENT_EVIDENCE)
        comparable: list[tuple[datetime, float]] = []
        incompatible = False
        for sample in ordered:
            captured = sample.captured_at.astimezone(UTC)
            if captured.astimezone(zone).date() != today or captured > now_utc:
                continue
            match = next((item for item in sample.quota_pools if item.id == pool.id), None)
            if match is None or match.used_fraction is None:
                continue
            if captured < bounds[0] or self._window_key(match) != self._window_key(pool):
                incompatible = True
                continue
            comparable.append((captured, match.used_fraction))
        if len(comparable) < 2:
            reason = (
                ForecastUnavailable.INCOMPATIBLE_WINDOW
                if incompatible
                else ForecastUnavailable.INSUFFICIENT_EVIDENCE
            )
            return self._unavailable(result, reason)
        first_time, first_used = comparable[0]
        last_time, last_used = comparable[-1]
        span = (last_time - first_time).total_seconds()
        if span < MIN_OBSERVATION_SECONDS:
            return self._unavailable(result, ForecastUnavailable.INSUFFICIENT_EVIDENCE)
        if any(right[1] < left[1] for left, right in zip(comparable, comparable[1:], strict=False)):
            return self._unavailable(result, ForecastUnavailable.INCOMPATIBLE_WINDOW)

        today_start = self._midnight(today, zone)
        today_end = self._midnight(today + timedelta(days=1), zone)
        day_seconds = (today_end - today_start).total_seconds()
        # The observed interval is an actual UTC duration; the local calendar
        # day's UTC length can be 23 or 25 hours at a DST transition.
        daily_rate = (last_used - first_used) * day_seconds / span
        points: list[DailyForecastPoint] = []
        projected = last_used
        for offset in range(MAX_POINTS):
            point_date = today + timedelta(days=offset)
            day_start = self._midnight(point_date, zone)
            day_end = self._midnight(point_date + timedelta(days=1), zone)
            endpoint = min(day_end, reset)
            interval_start = last_time if offset == 0 else day_start
            if endpoint <= interval_start:
                break
            day_length = (day_end - day_start).total_seconds()
            projected += daily_rate * (endpoint - interval_start).total_seconds() / day_length
            expected = self._budget.expected_fraction_at(pool, at=endpoint)
            if expected is None:
                return self._unavailable(result, ForecastUnavailable.TIMING_UNKNOWN)
            delta = projected - expected
            points.append(
                DailyForecastPoint(
                    date=point_date,
                    is_today=offset == 0,
                    projected_used_fraction=projected,
                    projected_remaining_fraction=1.0 - projected,
                    expected_used_fraction=expected,
                    delta_from_expected=delta,
                    state=self._budget.classify_pace_delta(delta),
                    exceeds_raw_quota=projected > 1.0,
                    ends_at_reset=endpoint == reset,
                )
            )
            if endpoint == reset:
                break
        if not points:
            return self._unavailable(result, ForecastUnavailable.RESET_PASSED)
        return DailyForecast(
            now,
            "today_observed_pace",
            "persisted",
            report.is_stale,
            tuple(points),
            observed_seconds=span,
            daily_rate=daily_rate,
        )

    @staticmethod
    def _window_key(pool: QuotaPool) -> tuple[datetime | None, datetime | None, int | None]:
        return (
            pool.starts_at.astimezone(UTC) if pool.starts_at else None,
            pool.resets_at.astimezone(UTC) if pool.resets_at else None,
            pool.window_seconds,
        )

    @staticmethod
    def _midnight(day: date, zone: ZoneInfo) -> datetime:
        return datetime.combine(day, time.min, zone).astimezone(UTC)

    @staticmethod
    def _unavailable(result: DailyForecast, reason: ForecastUnavailable) -> DailyForecast:
        return DailyForecast(
            result.generated_at,
            result.basis,
            result.source,
            result.stale,
            unavailable_reason=reason,
        )
