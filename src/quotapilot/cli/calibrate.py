"""Developer-facing deterministic calibration replay command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from quotapilot.calibration import (
    CalibrationError,
    ScenarioEvaluator,
    default_calibration_path,
    load_calibration_suite,
)

app = typer.Typer(help="Evaluate routing against synthetic calibration scenarios.")


@app.command("evaluate")
def evaluate(
    json_output: bool = typer.Option(False, "--json", help="Emit CalibrationReport JSON."),
    scenarios: Annotated[
        Path | None,
        typer.Option(
            "--scenarios",
            help="Path to a calibration scenario YAML file.",
        ),
    ] = None,
) -> None:
    """Replay the scenario suite through the existing pure Routing Engine."""
    try:
        suite = load_calibration_suite(scenarios or default_calibration_path())
        report = ScenarioEvaluator().evaluate(suite)
    except CalibrationError as exc:
        if json_output:
            typer.echo(
                json.dumps(
                    {"error": "calibration_unavailable", "message": str(exc)},
                    sort_keys=True,
                )
            )
        else:
            typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(report.model_dump_json(indent=2))
    else:
        metrics = report.metrics
        typer.echo("QuotaPilot Calibration")
        typer.echo(f"Scenarios                    {metrics.scenario_count}")
        typer.echo(f"Acceptable hits              {metrics.acceptable_hits}")
        typer.echo(
            f"Unacceptable recommendations {metrics.unacceptable_recommendations}"
        )
        typer.echo(f"Capability-floor violations {metrics.capability_floor_violations}")
        typer.echo(f"Anti-waste violations       {metrics.anti_waste_violations}")
        typer.echo(f"UNKNOWN quota violations    {metrics.unknown_quota_violations}")
        typer.echo(f"Unsupported effort          {metrics.unsupported_effort_violations}")
        typer.echo(f"Non-selectable model        {metrics.non_selectable_model_violations}")
        typer.echo(f"Determinism violations      {metrics.determinism_violations}")
        typer.echo(f"Routing failures            {metrics.routing_failures}")
        typer.echo(f"Result                      {'PASS' if report.passed else 'FAIL'}")
        for violation in report.violations:
            typer.echo(
                f"- {violation.scenario_id}: {violation.kind.value}: {violation.detail}"
            )
    if not report.passed:
        raise typer.Exit(code=1)
