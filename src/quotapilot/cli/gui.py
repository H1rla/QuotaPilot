"""Lazy GUI command so non-GUI CLI commands do not import Qt."""

from __future__ import annotations

import typer


def gui(
    smoke_test: bool = typer.Option(
        False,
        "--smoke-test",
        help="Load the packaged QML offscreen and exit.",
        hidden=True,
    ),
) -> None:
    """Launch the QuotaPilot desktop GUI."""
    from quotapilot.gui.app import run_gui

    raise typer.Exit(code=run_gui(smoke_test=smoke_test))

