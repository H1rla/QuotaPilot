"""Cheap persisted-state Waybar JSON output."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config import load_effective_config
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.services.status import StatusService, waybar_error, waybar_payload


def waybar(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Emit one valid Waybar JSON object using latest persisted state only."""

    async def run() -> str:
        try:
            effective = load_effective_config(path=config_path)
            profile_dir = (
                Path(effective.config.profiles.directory).expanduser()
                if effective.config.profiles.directory
                else default_profile_directory()
            )
            service = StatusService(
                SqliteSnapshotRepository(effective.config.database.path),
                BudgetEngine(effective.config.budget),
                CapabilityEnricher(),
                ModelProfileRegistry.from_directory(profile_dir),
            )
            report = await service.get_status(
                now=datetime.now(UTC),
                provider=effective.config.provider.default,
            )
            payload = waybar_payload(report) if report is not None else waybar_error(
                "no persisted snapshot"
            )
        except Exception:  # noqa: BLE001 - Waybar stdout must always be valid JSON
            payload = waybar_error()
        return payload.model_dump_json(by_alias=True)

    typer.echo(asyncio.run(run()))
