"""`quotapilot snapshot ...` — minimal persistence-facing CLI (Phase 3).

No budget/pacing/routing output belongs here — only capture-and-store and a
plain read-back of what's already persisted.
"""

from __future__ import annotations

import asyncio

import typer

from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository
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
def capture() -> None:
    """Capture a fresh snapshot from the OpenAI Codex provider and persist it."""

    async def run() -> None:
        provider = OpenAICodexProvider()
        repository = SqliteSnapshotRepository()
        service = SnapshotService(provider, repository)
        result = await service.capture_and_store()
        typer.echo(f"saved snapshot id={result.id}")
        typer.echo(_render(result.snapshot))

    asyncio.run(run())


@app.command("latest")
def latest() -> None:
    """Show the most recently persisted snapshot, if any."""

    async def run() -> None:
        repository = SqliteSnapshotRepository()
        snapshot = await repository.get_latest_snapshot()
        if snapshot is None:
            typer.echo("no snapshots stored yet")
            raise typer.Exit(code=1)
        typer.echo(_render(snapshot))

    asyncio.run(run())
