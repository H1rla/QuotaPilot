"""Primary privacy-safe operational status command."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config import ConfigError, load_effective_config
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.observability.models import StatusReport
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.services.status import StatusService


def _fraction(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.1%}"


def render_status(report: StatusReport) -> str:
    lines = [
        "QuotaPilot Status",
        f"Provider             {report.provider}",
        f"Source               {report.source.value}",
        f"Captured             {report.captured_at.isoformat()}",
        f"Snapshot age         {report.snapshot_age_seconds:.0f}s",
        f"Stale                {'yes' if report.is_stale else 'no'}",
    ]
    for pool in report.pools:
        lines.extend(
            [
                "",
                pool.name or pool.pool_id,
                f"Pool ID              {pool.pool_id}",
                f"Used                 {_fraction(pool.used_fraction)}",
                f"Remaining            {_fraction(pool.remaining_fraction)}",
                f"Today's budget       {_fraction(pool.today_budget_fraction)}",
                f"Budget state         {pool.state.value.upper()}",
                "Reset                "
                + (pool.resets_at.isoformat() if pool.resets_at else "unknown"),
            ]
        )
    lines.extend(
        [
            "",
            f"Effective pressure   {_fraction(report.effective_pressure)}",
            f"Binding pool         {report.binding_pool_id or 'unknown'}",
            f"Profile freshness    {report.profile.freshness.value}",
            f"Routable models      {report.profile.routable_model_count}",
        ]
    )
    if report.warnings:
        lines.append(f"Warnings             {', '.join(report.warnings)}")
    return "\n".join(lines)


def status(
    json_output: bool = typer.Option(False, "--json", help="Emit StatusReport JSON."),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Capture once from Codex before rendering; fall back to persisted state.",
    ),
    provider: str | None = typer.Option(None, help="Filter persisted state by provider."),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Show persisted quota, budget, and profile state without exposing identity."""
    try:
        effective = load_effective_config(
            path=config_path,
            cli_overrides={"provider.default": provider},
        )
    except ConfigError as exc:
        if json_output:
            typer.echo(json.dumps({"error": "invalid_config", "message": str(exc)}))
        else:
            typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    selected_provider = effective.config.provider.default
    if refresh and selected_provider not in {None, "openai-codex"}:
        message = "live refresh currently supports only provider 'openai-codex'"
        if json_output:
            typer.echo(json.dumps({"error": "invalid_provider", "message": message}))
        else:
            typer.echo(message, err=True)
        raise typer.Exit(code=2)

    async def run() -> None:
        try:
            repository = SqliteSnapshotRepository(effective.config.database.path)
            profile_dir = (
                Path(effective.config.profiles.directory).expanduser()
                if effective.config.profiles.directory
                else default_profile_directory()
            )
            service = StatusService(
                repository,
                BudgetEngine(effective.config.budget),
                CapabilityEnricher(),
                ModelProfileRegistry.from_directory(profile_dir),
            )
            report = await service.get_status(
                now=datetime.now(UTC),
                provider=selected_provider,
                refresh_provider=OpenAICodexProvider() if refresh else None,
            )
        except Exception as exc:  # noqa: BLE001 - expected CLI boundary
            message = "operational status is unavailable"
            if json_output:
                typer.echo(json.dumps({"error": "status_unavailable", "message": message}))
            else:
                typer.echo(message, err=True)
            raise typer.Exit(code=1) from exc

        if report is None:
            if json_output:
                typer.echo(json.dumps({"error": "no_snapshot"}, sort_keys=True))
            else:
                typer.echo("no snapshots stored yet")
            raise typer.Exit(code=1)
        if json_output:
            typer.echo(report.model_dump_json(indent=2))
        else:
            typer.echo(render_status(report))

    asyncio.run(run())
