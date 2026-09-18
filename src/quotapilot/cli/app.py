"""Root Typer application.

Further subcommands (`status`, `history`, `doctor`, `waybar`) are added in
later phases as their owning features are implemented.
"""

from __future__ import annotations

import typer

from quotapilot import __version__
from quotapilot.cli import snapshot
from quotapilot.cli.budget import budget
from quotapilot.cli.calibrate import app as calibrate_app
from quotapilot.cli.models import models
from quotapilot.cli.route import route

app = typer.Typer(
    name="quotapilot",
    help="Local usage-management and model-routing assistant for AI coding tools.",
    no_args_is_help=True,
)
app.add_typer(snapshot.app, name="snapshot")
app.add_typer(calibrate_app, name="calibrate")
app.command("budget")(budget)
app.command("models")(models)
app.command("route")(route)


@app.callback()
def callback() -> None:
    """Local usage-management and model-routing assistant for AI coding tools."""


@app.command()
def version() -> None:
    """Print the QuotaPilot version."""
    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
