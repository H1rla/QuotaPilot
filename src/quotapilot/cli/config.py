"""Safe inspection and validation of effective user configuration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

import typer

from quotapilot.config import ConfigError, EffectiveConfig, load_effective_config

app = typer.Typer(help="Inspect and validate strict QuotaPilot configuration.")


def _flatten(value: Mapping[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, item in value.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(item, Mapping):
            rows.extend(_flatten(item, dotted))
        else:
            rows.append((dotted, item))
    return rows


def _load_or_exit(path: Path | None, json_output: bool) -> EffectiveConfig:
    try:
        return load_effective_config(path=path)
    except ConfigError as exc:
        if json_output:
            typer.echo(json.dumps({"error": "invalid_config", "message": str(exc)}))
        else:
            typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


@app.command("show")
def show(
    json_output: bool = typer.Option(False, "--json", help="Emit effective config JSON."),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Validate this file instead of the platform default."),
    ] = None,
) -> None:
    """Display effective values and their winning configuration source."""
    effective = _load_or_exit(config_path, json_output)
    dumped = effective.config.model_dump(mode="json")
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "config_path": str(effective.path),
                    "config_file_present": effective.file_present,
                    "config": dumped,
                    "sources": effective.sources,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    typer.echo("QuotaPilot Configuration")
    typer.echo(f"Path                 {effective.path}")
    typer.echo(f"File present         {'yes' if effective.file_present else 'no'}")
    for dotted, value in _flatten(dumped):
        rendered = json.dumps(value, sort_keys=True)
        typer.echo(f"{dotted} = {rendered} [{effective.sources[dotted]}]")


@app.command("validate")
def validate(
    json_output: bool = typer.Option(False, "--json", help="Emit validation JSON."),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Validate this file instead of the platform default."),
    ] = None,
) -> None:
    """Validate configuration without contacting a provider or executing an agent."""
    effective = _load_or_exit(config_path, json_output)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "valid": True,
                    "config_path": str(effective.path),
                    "config_file_present": effective.file_present,
                },
                sort_keys=True,
            )
        )
    else:
        typer.echo(f"PASS: configuration is valid ({effective.path})")
