"""Privacy-safe inspection of enriched model routing capabilities."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from quotapilot.capabilities.enrichment import CapabilityEnricher, capability_views
from quotapilot.capabilities.errors import CapabilityProfileError
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config import ConfigError, load_effective_config
from quotapilot.history.errors import PersistenceError
from quotapilot.history.sqlite import SqliteSnapshotRepository


def _render_value(value: object) -> str:
    return "unknown" if value is None else str(value)


def models(
    json_output: bool = typer.Option(False, "--json", help="Emit model views as JSON."),
    provider: str | None = typer.Option(
        None, help="Filter the latest snapshot by provider."
    ),
    profile_dir: Annotated[
        Path | None,
        typer.Option(
            "--profile-dir",
            help="Directory containing versioned model-profile YAML files.",
        ),
    ] = None,
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Profile evaluation date in YYYY-MM-DD form (defaults to UTC today).",
    ),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Inspect enriched model metadata without fetching or exposing account data."""
    try:
        evaluated_on = date.fromisoformat(as_of) if as_of else datetime.now(UTC).date()
    except ValueError as exc:
        typer.echo("invalid --as-of date; expected YYYY-MM-DD", err=True)
        raise typer.Exit(code=2) from exc

    async def run() -> None:
        try:
            effective = load_effective_config(
                path=config_path,
                cli_overrides={
                    "provider.default": provider,
                    "profiles.directory": str(profile_dir) if profile_dir else None,
                },
            )
            selected_profile_dir = (
                Path(effective.config.profiles.directory).expanduser()
                if effective.config.profiles.directory
                else default_profile_directory()
            )
            registry = ModelProfileRegistry.from_directory(
                selected_profile_dir
            )
            repository = SqliteSnapshotRepository(effective.config.database.path)
            snapshot = await repository.get_latest_snapshot(
                provider=effective.config.provider.default
            )
            if snapshot is None:
                if json_output:
                    typer.echo(json.dumps({"error": "no_snapshot"}, sort_keys=True))
                else:
                    typer.echo("no snapshots stored yet")
                raise typer.Exit(code=1)
            enriched = CapabilityEnricher().enrich(
                snapshot.account.capabilities,
                registry,
                evaluated_on=evaluated_on,
            )
            views = capability_views(enriched)
        except ConfigError as exc:
            if json_output:
                typer.echo(
                    json.dumps(
                        {"error": "invalid_config", "message": str(exc)},
                        sort_keys=True,
                    )
                )
            else:
                typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except (CapabilityProfileError, PersistenceError) as exc:
            if json_output:
                typer.echo(
                    json.dumps(
                        {"error": "capability_profiles_unavailable", "message": str(exc)},
                        sort_keys=True,
                    )
                )
            else:
                typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "evaluated_on": evaluated_on.isoformat(),
                        "models": [view.model_dump(mode="json") for view in views],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return

        typer.echo("QuotaPilot Models")
        typer.echo(f"Profile date        {evaluated_on.isoformat()}")
        for view in views:
            typer.echo("")
            typer.echo(view.model_id)
            typer.echo(f"Selectable          {'yes' if view.selectable else 'no'}")
            typer.echo(f"Routable            {'yes' if view.routable else 'no'}")
            typer.echo(f"Relative power      {_render_value(view.relative_power)}")
            typer.echo(f"Relative cost       {_render_value(view.relative_cost)}")
            typer.echo(f"Relative latency    {_render_value(view.relative_latency)}")
            typer.echo(
                "Effort order        "
                + (", ".join(view.effort_order) if view.effort_order else "unknown")
            )
            typer.echo(f"Profile             {_render_value(view.profile_name)}")
            typer.echo(f"Profile source      {_render_value(view.profile_source)}")
            typer.echo(f"Confidence          {_render_value(view.profile_confidence)}")
            typer.echo(f"Freshness           {_render_value(view.freshness)}")
            for evidence in view.profile_evidence:
                typer.echo(f"Evidence            {evidence}")
            if view.warnings:
                typer.echo(f"Warnings            {', '.join(view.warnings)}")

    asyncio.run(run())
