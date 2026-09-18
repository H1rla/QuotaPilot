"""Advisory quota-aware model routing command."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.errors import CapabilityProfileError
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.history.errors import PersistenceError
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.errors import RoutingError
from quotapilot.routing.models import (
    RoutingRecommendation,
    TaskClass,
    TaskProfileOverrides,
)
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.routing import RoutingService


def render_routing_recommendation(recommendation: RoutingRecommendation) -> str:
    selected = next(
        score
        for score in recommendation.candidate_scores
        if score.model_id == recommendation.selected_model_id
    )
    lines = [
        "QuotaPilot Route",
        "",
        "Task",
        recommendation.task_profile.summary,
        f"Class               {recommendation.task_profile.task_class.value}",
        f"Profile source      {recommendation.task_profile.profile_source.value}",
        f"Difficulty          {recommendation.difficulty_score:.3f}",
        (
            f"Quota pressure      {recommendation.quota_pressure:.2f} "
            f"({recommendation.quota_pressure_source.value})"
        ),
        "",
        "Recommended",
        f"Model               {recommendation.selected_model_id}",
        f"Effort              {recommendation.selected_effort or 'unavailable'}",
        f"Utility             {selected.utility:.3f}",
        f"Confidence          {recommendation.confidence.value}",
        "",
        "Why",
    ]
    lines.extend(f"- {item}" for item in recommendation.explanation)
    lines.extend(["", "Escalation"])
    if recommendation.escalation_path:
        lines.extend(
            f"{index}. {step.model_id} / {step.effort or 'default'} — {step.reason}"
            for index, step in enumerate(recommendation.escalation_path, start=1)
        )
    else:
        lines.append("none")
    if recommendation.alternatives:
        lines.extend(["", "Alternatives"])
        lines.extend(
            f"- {step.model_id} / {step.effort or 'default'} — {step.reason}"
            for step in recommendation.alternatives
        )
    if recommendation.warnings:
        lines.extend(["", f"Warnings            {', '.join(recommendation.warnings)}"])
    return "\n".join(lines)


def route(
    task: str = typer.Argument(..., help="Task to profile and route."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit RoutingRecommendation JSON."
    ),
    provider: str | None = typer.Option(
        None, help="Filter the latest snapshot by provider."
    ),
    complexity: float | None = typer.Option(None, min=0.0, max=1.0),
    ambiguity: float | None = typer.Option(None, min=0.0, max=1.0),
    failure_cost: float | None = typer.Option(
        None, "--failure-cost", min=0.0, max=1.0
    ),
    verifiability: float | None = typer.Option(None, min=0.0, max=1.0),
    context_demand: float | None = typer.Option(
        None, "--context-demand", min=0.0, max=1.0
    ),
    latency_sensitivity: float | None = typer.Option(
        None, "--latency-sensitivity", min=0.0, max=1.0
    ),
    task_class: Annotated[TaskClass | None, typer.Option("--task-class")] = None,
    profile_dir: Annotated[
        Path | None,
        typer.Option(
            "--profile-dir",
            help="Directory containing versioned model-profile YAML files.",
        ),
    ] = None,
) -> None:
    """Recommend a model and effort without executing the task."""

    try:
        overrides = TaskProfileOverrides(
            complexity=complexity,
            ambiguity=ambiguity,
            failure_cost=failure_cost,
            verifiability=verifiability,
            context_demand=context_demand,
            latency_sensitivity=latency_sensitivity,
            task_class=task_class,
        )
    except ValidationError as exc:
        typer.echo(f"invalid task profile: {exc.errors()[0]['msg']}", err=True)
        raise typer.Exit(code=2) from exc

    async def run() -> None:
        repository = SqliteSnapshotRepository()
        try:
            registry = ModelProfileRegistry.from_directory(
                profile_dir or default_profile_directory()
            )
            service = RoutingService(
                repository,
                BudgetEngine(),
                RoutingEngine(),
                TaskProfiler(),
                CapabilityEnricher(),
                registry,
            )
            recommendation = await service.recommend_latest(
                task,
                now=datetime.now(UTC),
                overrides=overrides,
                provider=provider,
            )
        except ValidationError as exc:
            message = f"invalid task profile: {exc.errors()[0]['msg']}"
            if json_output:
                typer.echo(
                    json.dumps(
                        {"error": "invalid_task_profile", "message": message},
                        sort_keys=True,
                    )
                )
            else:
                typer.echo(message, err=True)
            raise typer.Exit(code=2) from exc
        except (CapabilityProfileError, RoutingError, PersistenceError) as exc:
            if json_output:
                typer.echo(
                    json.dumps(
                        {"error": "routing_unavailable", "message": str(exc)},
                        sort_keys=True,
                    )
                )
            else:
                typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        if recommendation is None:
            if json_output:
                typer.echo(json.dumps({"error": "no_snapshot"}, sort_keys=True))
            else:
                typer.echo("no snapshots stored yet")
            raise typer.Exit(code=1)
        if json_output:
            typer.echo(recommendation.model_dump_json(indent=2))
        else:
            typer.echo(render_routing_recommendation(recommendation))

    asyncio.run(run())
