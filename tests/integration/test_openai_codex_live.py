"""Opt-in live integration test against the real, authenticated `codex` CLI.

Skipped unless `QUOTAPILOT_INTEGRATION=1` is set, so `uv run pytest` stays
fully offline by default (design §23, project CLAUDE.md testing rules).
Never prints account identifiers/emails/tokens — only shapes and ranges.
"""

from __future__ import annotations

import os
from datetime import UTC
from pathlib import Path

import pytest

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.errors import NoRoutableModelError
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.snapshot import SnapshotService

pytestmark = pytest.mark.skipif(
    os.environ.get("QUOTAPILOT_INTEGRATION") != "1",
    reason="set QUOTAPILOT_INTEGRATION=1 to run against a real, authenticated codex CLI",
)


async def test_live_get_account_has_sane_shape() -> None:
    provider = OpenAICodexProvider()

    account = await provider.get_account()

    assert account.provider == "openai-codex"
    assert account.plan_name is None or isinstance(account.plan_name, str)


async def test_live_quota_pools_are_within_normalized_range() -> None:
    provider = OpenAICodexProvider()

    pools = await provider.get_quota_pools()

    assert isinstance(pools, list)
    for pool in pools:
        if pool.used_fraction is not None:
            assert 0.0 <= pool.used_fraction <= 1.0
        if pool.remaining_fraction is not None:
            assert 0.0 <= pool.remaining_fraction <= 1.0


async def test_live_healthcheck_ok() -> None:
    provider = OpenAICodexProvider()

    health = await provider.healthcheck()

    assert health.ok is True


async def test_live_capture_usage_is_one_coherent_snapshot() -> None:
    provider = OpenAICodexProvider()

    snapshot = await provider.capture_usage()

    assert snapshot.account.observed_at == snapshot.captured_at
    pool_ids = {p.id for p in snapshot.quota_pools}
    for binding in snapshot.quota_bindings:
        assert set(binding.quota_pool_ids) <= pool_ids
    # The raw-observation envelope must never carry the real account id in
    # the clear, even though AccountInfo.account_id does.
    raw_rate_limits = snapshot.metadata.get("raw_observation", {}).get("rate_limits_read", {})
    if "accountId" in raw_rate_limits and raw_rate_limits["accountId"] is not None:
        assert raw_rate_limits["accountId"] == "REDACTED"


async def test_live_capture_save_reload_round_trip(tmp_path: Path) -> None:
    """live capture -> temporary SQLite DB -> save -> reload -> compare."""
    provider = OpenAICodexProvider()
    repository = SqliteSnapshotRepository(tmp_path / "live_capture.db")
    service = SnapshotService(provider, repository)

    result = await service.capture_and_store()
    reloaded = await repository.get_snapshot(result.id)

    assert reloaded is not None
    if result.snapshot.account.account_id is None:
        assert reloaded.account.account_id is None
    else:
        assert reloaded.account.account_id != result.snapshot.account.account_id
    restored = reloaded.model_copy(
        update={
            "account": reloaded.account.model_copy(
                update={"account_id": result.snapshot.account.account_id}
            )
        }
    )
    assert restored == result.snapshot
    assert reloaded.captured_at == result.snapshot.captured_at
    pool_ids = {p.id for p in reloaded.quota_pools}
    for binding in reloaded.quota_bindings:
        assert set(binding.quota_pool_ids) <= pool_ids

    report = BudgetEngine().evaluate(reloaded, now=reloaded.captured_at)
    assert len(report.pools) == len(reloaded.quota_pools)
    for assessment in report.pools:
        if assessment.pressure is not None:
            assert 0.0 <= assessment.pressure <= 1.0
        if assessment.today_budget_fraction is not None:
            assert assessment.available_fraction is not None
            assert 0.0 <= assessment.today_budget_fraction <= assessment.available_fraction

    profile = TaskProfiler().profile("Review a repository change")
    routable_models = tuple(
        model
        for model in reloaded.account.capabilities.models
        if model.selectable and model.relative_power is not None
    )
    if not routable_models:
        # Current Codex discovery reports models but no QuotaPilot routing
        # heuristics. Refuse to fabricate power merely to make live routing pass.
        with pytest.raises(NoRoutableModelError):
            RoutingEngine().recommend(profile, report, reloaded.account.capabilities)
    else:
        recommendation = RoutingEngine().recommend(
            profile, report, reloaded.account.capabilities
        )
        assert recommendation.selected_model_id in {model.id for model in routable_models}

    registry = ModelProfileRegistry.from_directory(default_profile_directory())
    enriched = CapabilityEnricher().enrich(
        reloaded.account.capabilities,
        registry,
        evaluated_on=reloaded.captured_at.astimezone(UTC).date(),
    )
    profiled_routable = {
        model.id
        for model in enriched.models
        if model.selectable and model.relative_power is not None
    }
    if not profiled_routable:
        # A newly added or stale catalog is a safe typed no-route, not a reason
        # to guess metadata from a similar-looking model ID.
        with pytest.raises(NoRoutableModelError):
            RoutingEngine().recommend(profile, report, enriched)
    else:
        recommendation = RoutingEngine().recommend(profile, report, enriched)
        assert recommendation.selected_model_id in profiled_routable
        for model in enriched.models:
            if not model.metadata["routing_profile"]["matched"]:
                assert model.relative_power is None
