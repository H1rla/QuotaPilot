"""Human and stable JSON output for the latest persisted quota budget."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import typer
from pydantic import ValidationError

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import BudgetConfig, BudgetReport, PoolBudgetAssessment
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.services.budget import BudgetService


def _fraction(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "unavailable"
    return f"{value:+.1%}" if signed else f"{value:.1%}"


def _duration(seconds: int | None) -> str:
    if seconds is None:
        return "unavailable"
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _pool_lines(pool: PoolBudgetAssessment, reserve_fraction: float) -> list[str]:
    label = pool.pool_name or pool.pool_id
    reset = pool.resets_at.isoformat() if pool.resets_at is not None else "unavailable"
    return [
        "",
        label,
        f"Pool ID             {pool.pool_id}",
        f"Used                {_fraction(pool.actual_usage)}",
        f"Remaining           {_fraction(pool.remaining_fraction)}",
        f"Expected by now     {_fraction(pool.expected_usage)}",
        f"Pace delta          {_fraction(pool.pace_delta, signed=True)}",
        f"State               {pool.state.value.upper()}",
        f"Reserve             {_fraction(reserve_fraction)}",
        f"Available quota     {_fraction(pool.available_fraction)}",
        f"Today's budget      {_fraction(pool.today_budget_fraction)}",
        f"Reset               {reset}",
        f"Time remaining      {_duration(pool.time_until_reset_seconds)}",
    ]


def render_budget_report(report: BudgetReport) -> str:
    lines = [
        "QuotaPilot Budget",
        f"Captured            {report.captured_at.isoformat()}",
        f"Evaluated           {report.evaluated_at.isoformat()}",
        f"Stale               {'yes' if report.is_stale else 'no'}",
    ]
    for pool in report.pools:
        lines.extend(_pool_lines(pool, report.reserve_fraction))
    lines.extend(
        [
            "",
            f"Effective pressure  {_fraction(report.effective_pressure)}",
            f"Binding pool        {report.binding_pool_id or 'unavailable'}",
        ]
    )
    if report.warnings:
        lines.append(f"Warnings            {', '.join(report.warnings)}")
    return "\n".join(lines)


def budget(
    json_output: bool = typer.Option(False, "--json", help="Emit the BudgetReport as JSON."),
    provider: str | None = typer.Option(None, help="Filter the latest snapshot by provider."),
    reserve_fraction: float = typer.Option(0.10, help="Quota fraction reserved from use."),
    timezone: str = typer.Option("UTC", help="IANA timezone for calendar-day allocation."),
    stale_after_seconds: int = typer.Option(900, help="Age after which a snapshot is stale."),
) -> None:
    """Evaluate the latest persisted snapshot without fetching provider data."""

    try:
        config = BudgetConfig(
            reserve_fraction=reserve_fraction,
            timezone=timezone,
            stale_after_seconds=stale_after_seconds,
        )
    except ValidationError as exc:
        typer.echo(f"invalid budget configuration: {exc.errors()[0]['msg']}", err=True)
        raise typer.Exit(code=2) from exc

    async def run() -> None:
        repository = SqliteSnapshotRepository()
        service = BudgetService(repository, BudgetEngine(config))
        report = await service.get_latest_report(now=datetime.now(UTC), provider=provider)
        if report is None:
            if json_output:
                typer.echo(json.dumps({"error": "no_snapshot"}, sort_keys=True))
            else:
                typer.echo("no snapshots stored yet")
            raise typer.Exit(code=1)
        if json_output:
            typer.echo(report.model_dump_json(indent=2))
        else:
            typer.echo(render_budget_report(report))

    asyncio.run(run())
