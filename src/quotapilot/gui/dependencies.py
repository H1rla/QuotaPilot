"""GUI composition root for existing QuotaPilot services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config.loader import EffectiveConfig
from quotapilot.execution.adapters.codex_cli import CodexCliExecutionAdapter
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.execution import ExecutionService
from quotapilot.services.provider_status import ProviderStatusService
from quotapilot.services.routing import RoutingService
from quotapilot.services.status import StatusService


@dataclass(frozen=True, slots=True)
class GuiDependencies:
    effective: EffectiveConfig
    repository: SqliteSnapshotRepository
    budget_engine: BudgetEngine
    enricher: CapabilityEnricher
    registry: ModelProfileRegistry
    provider: OpenAICodexProvider
    provider_status_service: ProviderStatusService
    status_service: StatusService
    routing_service: RoutingService
    execution_service: ExecutionService


def build_dependencies(effective: EffectiveConfig) -> GuiDependencies:
    config = effective.config
    profile_dir = (
        Path(config.profiles.directory).expanduser()
        if config.profiles.directory
        else default_profile_directory()
    )
    repository = SqliteSnapshotRepository(config.database.path)
    budget_engine = BudgetEngine(config.budget)
    enricher = CapabilityEnricher()
    registry = ModelProfileRegistry.from_directory(profile_dir)
    provider = OpenAICodexProvider()
    status = StatusService(repository, budget_engine, enricher, registry)
    routing = RoutingService(
        repository,
        budget_engine,
        RoutingEngine(config.routing),
        TaskProfiler(),
        enricher,
        registry,
    )
    policy = config.execution
    adapter = CodexCliExecutionAdapter(max_output_bytes=policy.max_output_bytes)
    execution = ExecutionService(
        provider,
        routing,
        adapter,
        ExecutionPlanner(policy),
        policy,
    )
    return GuiDependencies(
        effective=effective,
        repository=repository,
        budget_engine=budget_engine,
        enricher=enricher,
        registry=registry,
        provider=provider,
        provider_status_service=ProviderStatusService(),
        status_service=status,
        routing_service=routing,
        execution_service=execution,
    )
