"""Root Typer application.

Subcommands (`status`, `route`, `history`, `doctor`, `waybar`) are added in
later phases once the budget/routing engines and providers exist.
"""

from __future__ import annotations

import typer

from quotapilot import __version__

app = typer.Typer(
    name="quotapilot",
    help="Local usage-management and model-routing assistant for AI coding tools.",
    no_args_is_help=True,
)


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
