"""Actionable, privacy-safe local diagnostics."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from quotapilot.config import ConfigError, load_effective_config
from quotapilot.observability.doctor import (
    DoctorReport,
    DoctorService,
    DoctorStatus,
    invalid_config_report,
)


def render_doctor(report: DoctorReport) -> str:
    lines = ["QuotaPilot Doctor"]
    for check in report.checks:
        lines.append(f"{check.status.value:4}  {check.name}: {check.message}")
        if check.remediation:
            lines.append(f"      Remediation: {check.remediation}")
    lines.append(f"Overall: {'PASS' if report.healthy else 'FAIL'}")
    return "\n".join(lines)


def doctor(
    json_output: bool = typer.Option(False, "--json", help="Emit DoctorReport JSON."),
    live: bool = typer.Option(
        False,
        "--live",
        help="Explicitly perform an authenticated provider capture health check.",
    ),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Diagnose configuration, local data, profiles, Codex, and output surfaces."""
    now = datetime.now(UTC)
    try:
        effective = load_effective_config(path=config_path)
    except ConfigError:
        report = invalid_config_report(now=now)
    else:
        report = asyncio.run(DoctorService(effective).run(now=now, live=live))

    if json_output:
        typer.echo(report.model_dump_json(indent=2))
    else:
        typer.echo(render_doctor(report))
    if any(check.status is DoctorStatus.FAIL for check in report.checks):
        raise typer.Exit(code=1)
