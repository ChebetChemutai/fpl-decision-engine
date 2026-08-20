"""Command-line interface for the FPL Decision Engine.

Phase 1 scope only: prove the project is wired correctly end to end
(package installs, console script runs, config loads). Domain commands
(e.g. `fpl squad recommend`) are added starting Phase 2/9.
"""

from __future__ import annotations

import typer

from fpl_engine import __version__
from fpl_engine.config import get_settings

app = typer.Typer(
    name="fpl",
    help="FPL AI Decision Engine — command-line interface.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed package version."""
    typer.echo(__version__)


@app.command()
def info() -> None:
    """Print resolved configuration — useful for verifying environment setup."""
    settings = get_settings()
    typer.echo(f"environment : {settings.environment.value}")
    typer.echo(f"log_level   : {settings.log_level}")
    typer.echo(f"data_dir    : {settings.data_dir}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
