"""Controlled dry-run and explicitly approved external-agent execution."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.errors import CapabilityProfileError
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config import ConfigError, load_effective_config
from quotapilot.execution.adapters.codex_cli import CodexCliExecutionAdapter
from quotapilot.execution.errors import ExecutionError
from quotapilot.execution.models import (
    ExecutionMode,
    ExecutionPlan,
    ExecutionPolicy,
    ExecutionResult,
)
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.history.errors import PersistenceError
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.providers.openai_codex.errors import CodexProviderError
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.errors import RoutingError
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.execution import ExecutionService
from quotapilot.services.routing import RoutingService


def render_execution_plan(plan: ExecutionPlan) -> str:
    pressure = "unknown" if plan.budget_pressure is None else f"{plan.budget_pressure:.2f}"
    lines = [
        "QuotaPilot Execute",
        "",
        f"Execution ID        {plan.execution_id}",
        f"Task class          {plan.task_class.value}",
        f"Task hash           {plan.task_hash}",
        f"Recommended model   {plan.model_id}",
        f"Recommended effort  {plan.effort or 'unavailable'}",
        f"Quota pressure      {pressure}",
        f"Binding pool        {plan.binding_pool_id or 'unavailable'}",
        f"Execution adapter   {plan.adapter_name}",
        f"Working directory   {plan.working_directory}",
        f"Approval required   {'yes' if plan.requires_confirmation else 'no'}",
        f"Timeout             {plan.timeout_seconds}s",
        f"Maximum attempts    {plan.max_attempts}",
        f"Dry run             {'yes' if plan.dry_run else 'no'}",
        "",
        "Escalation path",
    ]
    if plan.escalation_path:
        lines.extend(
            f"{index}. {step.model_id} / {step.effort or 'default'} — {step.reason}"
            for index, step in enumerate(plan.escalation_path, start=1)
        )
    else:
        lines.append("none")
    lines.extend(["", "Adapter command", " ".join(plan.command_preview)])
    if plan.warnings:
        lines.extend(["", f"Warnings            {', '.join(plan.warnings)}"])
    return "\n".join(lines)


def render_execution_result(result: ExecutionResult) -> str:
    lines = [
        "QuotaPilot Execution Result",
        "",
        f"Status              {result.status.value}",
        f"Model               {result.model_id}",
        f"Effort              {result.effort or 'unavailable'}",
        f"Attempts            {result.attempt_count}",
        f"Retries             {result.retry_count}",
        f"Escalations         {result.escalation_count}",
        f"Failure class       {result.failure_class.value if result.failure_class else 'none'}",
    ]
    if result.message:
        lines.append(f"Message             {result.message}")
    if result.stdout_summary:
        lines.extend(["", "Bounded stdout tail", result.stdout_summary])
    if result.stderr_summary:
        lines.extend(["", "Bounded stderr tail", result.stderr_summary])
    return "\n".join(lines)


def execute(
    task: str = typer.Argument(..., help="Task to route and optionally execute."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the safe execution plan without invoking an external agent.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit safe ExecutionPlan JSON (dry-run only).",
    ),
    working_directory: Annotated[
        Path,
        typer.Option(
            "--working-directory",
            "--cwd",
            help="Existing directory in which the external agent may operate.",
        ),
    ] = Path("."),
    approval_mode: Annotated[
        ExecutionMode | None,
        typer.Option(
            "--approval-mode",
            help="Execution authorization policy; real execution defaults to confirmation.",
        ),
    ] = None,
    max_attempts: Annotated[
        int | None, typer.Option("--max-attempts", min=1, max=10)
    ] = None,
    max_same_step_retries: Annotated[
        int | None, typer.Option("--max-same-step-retries", min=0, max=5)
    ] = None,
    timeout_seconds: Annotated[
        int | None, typer.Option("--timeout-seconds", min=1, max=86_400)
    ] = None,
    profile_dir: Annotated[
        Path | None,
        typer.Option(
            "--profile-dir",
            help="Directory containing versioned model-profile YAML files.",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Plan safely, then execute only when policy and explicit approval permit it."""
    if json_output and not dry_run:
        typer.echo("--json is supported only with --dry-run", err=True)
        raise typer.Exit(code=2)

    try:
        effective = load_effective_config(
            path=config_path,
            cli_overrides={
                "execution.mode": approval_mode,
                "execution.max_attempts": max_attempts,
                "execution.max_same_step_retries": max_same_step_retries,
                "execution.timeout_seconds": timeout_seconds,
                "profiles.directory": str(profile_dir) if profile_dir else None,
            },
        )
        if effective.config.provider.default not in {None, "openai-codex"}:
            raise ConfigError(
                "controlled execution currently supports only provider 'openai-codex'"
            )
        policy: ExecutionPolicy = effective.config.execution
    except ConfigError as exc:
        typer.echo(f"invalid execution policy: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    async def run() -> None:
        try:
            selected_profile_dir = (
                Path(effective.config.profiles.directory).expanduser()
                if effective.config.profiles.directory
                else default_profile_directory()
            )
            repository = SqliteSnapshotRepository(effective.config.database.path)
            registry = ModelProfileRegistry.from_directory(
                selected_profile_dir
            )
            routing = RoutingService(
                repository,
                BudgetEngine(effective.config.budget),
                RoutingEngine(effective.config.routing),
                TaskProfiler(),
                CapabilityEnricher(),
                registry,
            )
            adapter = CodexCliExecutionAdapter(max_output_bytes=policy.max_output_bytes)
            service = ExecutionService(
                OpenAICodexProvider(),
                routing,
                adapter,
                ExecutionPlanner(policy),
                policy,
            )
            plan = await service.create_plan(
                task,
                working_directory=working_directory,
                dry_run=dry_run,
            )
            if dry_run:
                if json_output:
                    typer.echo(plan.model_dump_json(indent=2))
                else:
                    typer.echo(render_execution_plan(plan))
                return

            typer.echo(render_execution_plan(plan))

            async def approve(candidate: ExecutionPlan) -> bool:
                if candidate.execution_id != plan.execution_id:
                    typer.echo("\nMaterial escalation plan")
                    typer.echo(render_execution_plan(candidate))
                return typer.confirm("Execute this exact plan?", default=False)

            result = await service.run_plan(plan, approval_handler=approve)
            typer.echo("")
            typer.echo(render_execution_result(result))
            if result.status.value != "succeeded":
                raise typer.Exit(code=1)
        except ValidationError as exc:
            typer.echo(f"invalid execution input: {exc.errors()[0]['msg']}", err=True)
            raise typer.Exit(code=2) from exc
        except (
            CapabilityProfileError,
            CodexProviderError,
            ExecutionError,
            PersistenceError,
            RoutingError,
            OSError,
        ) as exc:
            if json_output:
                typer.echo(
                    json.dumps(
                        {"error": "execution_unavailable", "message": str(exc)},
                        sort_keys=True,
                    )
                )
            else:
                typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    asyncio.run(run())
