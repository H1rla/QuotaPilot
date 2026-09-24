"""Lazy TUI command so established CLI commands do not import Textual."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer


def tui(
    smoke_test: bool = typer.Option(
        False,
        "--smoke-test",
        help="Mount the packaged TUI headlessly and exit.",
        hidden=True,
    ),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Use this config file instead of the platform default."),
    ] = None,
) -> None:
    """Launch the persistent QuotaPilot terminal UI."""
    if not smoke_test and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        typer.echo(
            "quotapilot tui requires an interactive terminal; use one-shot CLI commands here",
            err=True,
        )
        raise typer.Exit(code=2)

    from quotapilot.config import ConfigError
    from quotapilot.tui.app import run_tui

    try:
        code = run_tui(smoke_test=smoke_test, config_path=config_path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    raise typer.Exit(code=code)
