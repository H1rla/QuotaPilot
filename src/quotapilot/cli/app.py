"""Root Typer application."""

from __future__ import annotations

import logging

import typer

from quotapilot import __version__
from quotapilot.cli import snapshot
from quotapilot.cli.budget import budget
from quotapilot.cli.calibrate import app as calibrate_app
from quotapilot.cli.config import app as config_app
from quotapilot.cli.doctor import doctor
from quotapilot.cli.execute import execute
from quotapilot.cli.models import models
from quotapilot.cli.route import route
from quotapilot.cli.status import status
from quotapilot.cli.waybar import waybar

app = typer.Typer(
    name="quotapilot",
    help="Local usage-management and model-routing assistant for AI coding tools.",
    no_args_is_help=True,
)
app.add_typer(snapshot.app, name="snapshot")
app.add_typer(calibrate_app, name="calibrate")
app.add_typer(config_app, name="config")
app.command("budget")(budget)
app.command("models")(models)
app.command("route")(route)
app.command("execute")(execute)
app.command("status")(status)
app.command("waybar")(waybar)
app.command("doctor")(doctor)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def callback(
    version_option: bool = typer.Option(
        False,
        "--version",
        help="Show the packaged version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable diagnostic logging to stderr (secrets remain redacted).",
    ),
) -> None:
    """Local usage-management and model-routing assistant for AI coding tools."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING)


@app.command()
def version() -> None:
    """Print the QuotaPilot version."""
    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
