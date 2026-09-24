"""TUI composition root over existing QuotaPilot services."""

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
from quotapilot.observability.doctor import DoctorService
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.execution import ExecutionService
from quotapilot.services.provider_status import ProviderStatusService
from quotapilot.services.routing import RoutingService
from quotapilot.services.status import StatusService


@dataclass(frozen=True, slots=True)
class TuiDependencies:
    effective: EffectiveConfig
    provider: OpenAICodexProvider
    provider_status_service: ProviderStatusService
    status_service: StatusService
    repository: SqliteSnapshotRepository | None = None
    enricher: CapabilityEnricher | None = None
    registry: ModelProfileRegistry | None = None
    routing_service: RoutingService | None = None
    execution_service: ExecutionService | None = None
    budget_engine: BudgetEngine | None = None
    doctor_service: DoctorService | None = None


def build_dependencies(effective: EffectiveConfig) -> TuiDependencies:
    config = effective.config
    profile_dir = (
        Path(config.profiles.directory).expanduser()
        if config.profiles.directory
        else default_profile_directory()
    )
    repository = SqliteSnapshotRepository(config.database.path)
    provider = OpenAICodexProvider()
    budget = BudgetEngine(config.budget)
    enricher = CapabilityEnricher()
    registry = ModelProfileRegistry.from_directory(profile_dir)
    routing = RoutingService(
        repository, budget, RoutingEngine(config.routing), TaskProfiler(), enricher, registry
    )
    policy = config.execution
    return TuiDependencies(
        effective=effective,
        provider=provider,
        provider_status_service=ProviderStatusService(),
        status_service=StatusService(
            repository,
            budget,
            enricher,
            registry,
        ),
        repository=repository,
        enricher=enricher,
        registry=registry,
        routing_service=routing,
        execution_service=ExecutionService(
            provider,
            routing,
            CodexCliExecutionAdapter(max_output_bytes=policy.max_output_bytes),
            ExecutionPlanner(policy),
            policy,
        ),
        budget_engine=budget,
        doctor_service=DoctorService(effective),
    )
