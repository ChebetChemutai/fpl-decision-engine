"""Command-line interface for the FPL Decision Engine."""

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


@app.command()
def ingest(
    gameweek: int = typer.Option(..., help="Gameweek number to tag this snapshot with."),
) -> None:
    """Pull current bootstrap-static + fixtures data and save a raw snapshot.

    Must be run somewhere that can reach fantasy.premierleague.com — the CI
    sandbox this was developed in cannot (see docs/architecture.md Sec 4/18).
    """
    from fpl_engine.data.fpl_client import FplClient
    from fpl_engine.data.snapshot import write_snapshot

    settings = get_settings()
    with FplClient() as client:
        bootstrap = client.fetch_bootstrap()
        fixtures = client.fetch_fixtures(event=gameweek)

    season = _current_season_label(bootstrap)
    bootstrap_path = write_snapshot(
        raw_dir=settings.raw_dir,
        source="fpl_bootstrap",
        season=season,
        gameweek=gameweek,
        payload=bootstrap,
    )
    fixtures_path = write_snapshot(
        raw_dir=settings.raw_dir,
        source="fpl_fixtures",
        season=season,
        gameweek=gameweek,
        payload={"fixtures": fixtures},
    )
    typer.echo(f"bootstrap snapshot : {bootstrap_path}")
    typer.echo(f"fixtures snapshot  : {fixtures_path}")
    typer.echo(f"players ingested   : {len(bootstrap.get('elements', []))}")


@app.command("squad")
def squad_recommend(
    gameweek: int = typer.Option(..., help="Gameweek to build the recommendation for."),
    budget: float = typer.Option(100.0, help="Total squad budget in £m."),
) -> None:
    """Build and print a baseline squad recommendation from the latest snapshot.

    Run `fpl ingest --gameweek N` first. This is the Phase 1.5 baseline model
    — see docs/architecture.md Sec 17. It is explicitly a floor, not the
    target architecture.
    """
    from fpl_engine.baseline.squad_builder import build_squad
    from fpl_engine.data.snapshot import read_latest_snapshot_any_season
    from fpl_engine.domain.models import Player

    settings = get_settings()
    try:
        envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_bootstrap", gameweek=gameweek
        )
    except FileNotFoundError:
        typer.echo(
            f"No snapshot found for GW{gameweek}. "
            f"Run `fpl ingest --gameweek {gameweek}` first."
        )
        raise typer.Exit(code=1) from None

    elements = envelope["payload"]["elements"]
    players = [Player.from_bootstrap_element(e) for e in elements]

    squad = build_squad(players, budget=budget)

    captured_at = envelope["captured_at"]
    typer.echo(f"[BASELINE MODEL — Phase 1.5, GW{gameweek}] captured_at={captured_at}")
    typer.echo(f"Squad cost: £{squad.total_price}m / £{budget}m\n")

    typer.echo("STARTING XI")
    for p in sorted(squad.starting_xi, key=lambda x: x.position):
        if p.id == squad.captain.id:
            marker = " (C)"
        elif p.id == squad.vice_captain.id:
            marker = " (VC)"
        else:
            marker = ""
        typer.echo(
            f"  {p.position.name:<4} {p.web_name:<20} £{p.price:>4.1f}m "
            f" ep_next={p.ep_next:>4.1f}{marker}"
        )

    typer.echo("\nBENCH (in order)")
    for i, p in enumerate(squad.bench, start=1):
        typer.echo(
            f"  {i}. {p.position.name:<4} {p.web_name:<20} £{p.price:>4.1f}m "
            f" ep_next={p.ep_next:>4.1f}"
        )


def _current_season_label(bootstrap: dict[str, object]) -> str:
    """Derive a 'YYYY_YY' season label from the bootstrap payload's static
    content URL, falling back to a generic label if the shape changes."""
    game_config = bootstrap.get("game_config")
    settings_block = game_config.get("settings") if isinstance(game_config, dict) else None
    static_url = ""
    if isinstance(settings_block, dict):
        static_url = str(settings_block.get("static_content_url", ""))
    for part in static_url.split("/"):
        if part.count("_") == 1 and all(chunk.isdigit() for chunk in part.split("_")):
            return part
    return "unknown_season"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
