"""`quotapilot snapshot ...` — minimal persistence-facing CLI (Phase 3).

No budget/pacing/routing output belongs here — only capture-and-store and a
plain read-back of what's already persisted.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from quotapilot.config import ConfigError, load_effective_config
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.errors import PersistenceError
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.providers.openai_codex.errors import CodexProviderError
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.services.snapshot import SnapshotService

app = typer.Typer(help="Capture and inspect persisted usage snapshots.")


def _render(snapshot: UsageSnapshot) -> str:
    lines = [
        f"provider     {snapshot.account.provider}",
        f"plan_name    {snapshot.account.plan_name}",
        f"captured_at  {snapshot.captured_at.isoformat()}",
        f"quota_pools  {len(snapshot.quota_pools)}",
        f"bindings     {len(snapshot.quota_bindings)}",
    ]
    for pool in snapshot.quota_pools:
        used = f"{pool.used_fraction:.0%}" if pool.used_fraction is not None else "unknown"
        lines.append(f"  pool {pool.id!r}: kind={pool.kind} scope={pool.scope} used={used}")
    return "\n".join(lines)


@app.command("capture")
def capture(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Capture a fresh snapshot from the OpenAI Codex provider and persist it."""

    async def run() -> None:
        try:
            effective = load_effective_config(path=config_path)
            if effective.config.provider.default not in {None, "openai-codex"}:
                raise ConfigError(
                    "snapshot capture currently supports only provider 'openai-codex'"
                )
            provider = OpenAICodexProvider()
            repository = SqliteSnapshotRepository(effective.config.database.path)
            service = SnapshotService(provider, repository)
            result = await service.capture_and_store()
        except ConfigError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except (CodexProviderError, PersistenceError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"saved snapshot id={result.id}")
        typer.echo(_render(result.snapshot))

    asyncio.run(run())


@app.command("latest")
def latest(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Show the most recently persisted snapshot, if any."""

    async def run() -> None:
        try:
            effective = load_effective_config(path=config_path)
        except ConfigError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        repository = SqliteSnapshotRepository(effective.config.database.path)
        try:
            snapshot = await repository.get_latest_snapshot(
                provider=effective.config.provider.default
            )
        except PersistenceError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        if snapshot is None:
            typer.echo("no snapshots stored yet")
            raise typer.Exit(code=1)
        typer.echo(_render(snapshot))

    asyncio.run(run())
