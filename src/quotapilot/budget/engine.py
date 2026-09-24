"""Pure quota pace, reserve, allocation, and multi-window calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from quotapilot.budget.errors import BudgetEvaluationError
from quotapilot.budget.models import (
    BudgetConfig,
    BudgetReport,
    BudgetState,
    PoolBudgetAssessment,
    RemainingSource,
    TimingSource,
)
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot


@dataclass(frozen=True, slots=True)
class _Timing:
    start: datetime
    reset: datetime
    source: TimingSource


class BudgetEngine:
    """Evaluate one normalized snapshot under one explicit user policy."""

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self._config = config or BudgetConfig()

    @property
    def config(self) -> BudgetConfig:
        return self._config

    def evaluate(self, snapshot: UsageSnapshot, *, now: datetime) -> BudgetReport:
        if now.utcoffset() is None:
            raise BudgetEvaluationError("evaluation time must be timezone-aware")
        now_utc = now.astimezone(UTC)

        pool_ids = [pool.id for pool in snapshot.quota_pools]
        if len(pool_ids) != len(set(pool_ids)):
            raise BudgetEvaluationError("quota pool ids must be unique")

        assessments = tuple(self._assess_pool(pool, now_utc) for pool in snapshot.quota_pools)
        binding = self._select_binding_pool(assessments)

        snapshot_age = (now_utc - snapshot.captured_at.astimezone(UTC)).total_seconds()
        report_warnings: list[str] = []
        is_stale = snapshot_age > self._config.stale_after_seconds
        if is_stale:
            report_warnings.append("snapshot_stale")
        if snapshot_age < 0:
            report_warnings.append("snapshot_captured_in_future")
        if not assessments:
            report_warnings.append("no_quota_pools")

        unknown_count = sum(item.state is BudgetState.UNKNOWN for item in assessments)
        if unknown_count:
            report_warnings.append(f"unknown_pool_count:{unknown_count}")

        return BudgetReport(
            captured_at=snapshot.captured_at,
            evaluated_at=now,
            snapshot_age_seconds=snapshot_age,
            is_stale=is_stale,
            reserve_fraction=self._config.reserve_fraction,
            timezone=self._config.timezone,
            pools=assessments,
            effective_pressure=binding.pressure if binding is not None else None,
            binding_pool_id=binding.pool_id if binding is not None else None,
            warnings=tuple(report_warnings),
        )

    def _assess_pool(self, pool: QuotaPool, now_utc: datetime) -> PoolBudgetAssessment:
        warnings: list[str] = []
        actual = pool.used_fraction
        if actual is None:
            warnings.append("actual_usage_unavailable")

        remaining, remaining_source = self._remaining(pool)
        if (
            pool.used_fraction is not None
            and pool.remaining_fraction is not None
            and not math.isclose(
                pool.used_fraction + pool.remaining_fraction,
                1.0,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ):
            warnings.append("used_remaining_inconsistent")

        available = (
            max(0.0, remaining - self._config.reserve_fraction)
            if remaining is not None
            else None
        )

        timing = self._resolve_timing(pool, warnings)
        progress: float | None = None
        expected: float | None = None
        pace_delta: float | None = None
        state = BudgetState.UNKNOWN
        pressure: float | None = None

        if timing is not None:
            raw_progress = (now_utc - timing.start).total_seconds() / (
                timing.reset - timing.start
            ).total_seconds()
            progress = min(1.0, max(0.0, raw_progress))
            expected = progress * (1.0 - self._config.reserve_fraction)
            if now_utc < timing.start:
                warnings.append("evaluation_before_window_start")
            if now_utc >= timing.reset:
                warnings.append("reset_time_passed")
            if actual is not None:
                pace_delta = actual - expected
                state = self.classify_pace_delta(pace_delta)
                pressure = self._pressure(state)
        else:
            warnings.append("pace_timing_unavailable")

        reset = pool.resets_at
        time_until_reset = None
        if reset is not None:
            reset_utc = reset.astimezone(UTC)
            time_until_reset = max(0, math.floor((reset_utc - now_utc).total_seconds()))

        today_budget = self._today_budget(
            available=available,
            reset=reset,
            period_start=timing.start if timing is not None else None,
            now_utc=now_utc,
            warnings=warnings,
        )

        return PoolBudgetAssessment(
            pool_id=pool.id,
            pool_name=pool.raw_name,
            resets_at=reset,
            actual_usage=actual,
            expected_usage=expected,
            pace_delta=pace_delta,
            remaining_fraction=remaining,
            remaining_source=remaining_source,
            available_fraction=available,
            today_budget_fraction=today_budget,
            window_progress=progress,
            time_until_reset_seconds=time_until_reset,
            state=state,
            pressure=pressure,
            timing_source=timing.source if timing is not None else None,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _remaining(pool: QuotaPool) -> tuple[float | None, RemainingSource | None]:
        if pool.remaining_fraction is not None:
            return pool.remaining_fraction, RemainingSource.REPORTED
        if pool.used_fraction is not None:
            return 1.0 - pool.used_fraction, RemainingSource.DERIVED_USED_FRACTION
        return None, None

    @staticmethod
    def _resolve_timing(pool: QuotaPool, warnings: list[str]) -> _Timing | None:
        if pool.starts_at is not None and pool.resets_at is not None:
            start_utc = pool.starts_at.astimezone(UTC)
            reset_utc = pool.resets_at.astimezone(UTC)
            if reset_utc <= start_utc:
                warnings.append("invalid_window_timing")
                return None
            if pool.window_seconds is not None and not math.isclose(
                (reset_utc - start_utc).total_seconds(),
                pool.window_seconds,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                warnings.append("window_seconds_conflicts_with_start_reset")
            return _Timing(
                start=start_utc,
                reset=reset_utc,
                source=TimingSource.START_RESET,
            )

        if pool.starts_at is None and pool.resets_at is not None:
            if pool.window_seconds is None:
                return None
            if pool.window_seconds <= 0:
                warnings.append("invalid_window_timing")
                return None
            reset_utc = pool.resets_at.astimezone(UTC)
            return _Timing(
                start=reset_utc - timedelta(seconds=pool.window_seconds),
                reset=reset_utc,
                source=TimingSource.DERIVED_WINDOW_SECONDS,
            )

        return None

    def classify_pace_delta(self, pace_delta: float) -> BudgetState:
        """Apply the configured budget policy to an observed or projected delta."""
        config = self._config
        if pace_delta < config.very_under_threshold:
            return BudgetState.VERY_UNDER
        if pace_delta < config.under_threshold:
            return BudgetState.UNDER
        if pace_delta <= config.over_threshold:
            return BudgetState.ON_TRACK
        if pace_delta <= config.critical_threshold:
            return BudgetState.OVER
        return BudgetState.CRITICAL

    def expected_fraction_at(self, pool: QuotaPool, *, at: datetime) -> float | None:
        """Return reserve-aware cumulative expected usage at an instant."""
        bounds = self.window_bounds(pool)
        if bounds is None:
            return None
        start, reset = bounds
        at_utc = at.astimezone(UTC)
        progress = (at_utc - start).total_seconds() / (reset - start).total_seconds()
        return min(1.0, max(0.0, progress)) * (1.0 - self._config.reserve_fraction)

    def window_bounds(self, pool: QuotaPool) -> tuple[datetime, datetime] | None:
        """Expose the same authoritative UTC window used by current-state evaluation."""
        timing = self._resolve_timing(pool, [])
        return (timing.start, timing.reset) if timing is not None else None

    def _pressure(self, state: BudgetState) -> float | None:
        return {
            BudgetState.VERY_UNDER: self._config.very_under_pressure,
            BudgetState.UNDER: self._config.under_pressure,
            BudgetState.ON_TRACK: self._config.on_track_pressure,
            BudgetState.OVER: self._config.over_pressure,
            BudgetState.CRITICAL: self._config.critical_pressure,
            BudgetState.UNKNOWN: None,
        }[state]

    def _today_budget(
        self,
        *,
        available: float | None,
        reset: datetime | None,
        period_start: datetime | None,
        now_utc: datetime,
        warnings: list[str],
    ) -> float | None:
        if available is None or reset is None:
            return None
        reset_utc = reset.astimezone(UTC)
        if reset_utc <= now_utc:
            return 0.0
        if period_start is not None and now_utc < period_start:
            return None

        timezone = ZoneInfo(self._config.timezone)
        local_now = now_utc.astimezone(timezone)
        local_reset = reset_utc.astimezone(timezone)
        first_date = local_now.date()
        last_date = local_reset.date()
        if local_reset.timetz().replace(tzinfo=None) == time.min:
            last_date -= timedelta(days=1)
        if last_date < first_date:
            return 0.0

        day_count = (last_date - first_date).days + 1
        normalized_total, normalized_today = self._normalized_weight_total(
            first_weekday=first_date.weekday(),
            day_count=day_count,
        )
        if normalized_total <= 0.0:
            warnings.append("remaining_day_weights_zero")
            return None

        return available * normalized_today / normalized_total

    def _normalized_weight_total(
        self, *, first_weekday: int, day_count: int
    ) -> tuple[float, float]:
        """Return interval and first-day weights in O(1) calendar operations."""
        weights = self._config.weekday_weights.as_tuple()
        full_weeks, remainder = divmod(day_count, 7)
        if full_weeks:
            max_weight = max(weights)
        else:
            # At most six entries: use only weekdays actually in the interval,
            # matching the former per-date normalization even for extreme weights.
            max_weight = max(
                weights[(first_weekday + offset) % 7] for offset in range(remainder)
            )
        if max_weight <= 0.0:
            return 0.0, 0.0

        normalized = tuple(weight / max_weight for weight in weights)
        total = full_weeks * sum(normalized)
        total += sum(normalized[(first_weekday + offset) % 7] for offset in range(remainder))
        return total, normalized[first_weekday]

    @staticmethod
    def _select_binding_pool(
        assessments: tuple[PoolBudgetAssessment, ...],
    ) -> PoolBudgetAssessment | None:
        evaluable = [item for item in assessments if item.pressure is not None]
        if not evaluable:
            return None

        def binding_key(item: PoolBudgetAssessment) -> tuple[float, float, str]:
            assert item.pressure is not None
            return (
                -item.pressure,
                item.remaining_fraction
                if item.remaining_fraction is not None
                else math.inf,
                item.pool_id,
            )

        return min(
            evaluable,
            key=binding_key,
        )
