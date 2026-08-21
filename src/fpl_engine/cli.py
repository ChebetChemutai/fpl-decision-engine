"""Command-line interface for the FPL Decision Engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from fpl_engine import __version__
from fpl_engine.config import get_settings

if TYPE_CHECKING:
    from fpl_engine.config import Settings
    from fpl_engine.domain.models import Player, ScoredPlayer

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
    mode: str = typer.Option(
        "enhanced",
        help=(
            "'baseline' (ep_next + availability only — the reproducible control "
            "group) or 'enhanced' (adds fixture difficulty and a history-based "
            "cold-start prior on top of the same baseline)."
        ),
    ),
) -> None:
    """Build and print a squad recommendation from the latest snapshot.

    Run `fpl ingest --gameweek N` first (and `fpl ingest-history` for the
    historical prior, optional). 'enhanced' is the default recommendation
    mode; 'baseline' reproduces the original Phase 1.5 ep_next-only model
    exactly, so the two can be compared directly — see
    docs/architecture.md Sec 18.
    """
    from fpl_engine.baseline.squad_builder import build_squad
    from fpl_engine.data.snapshot import read_latest_snapshot_any_season
    from fpl_engine.domain.models import Player

    if mode not in ("baseline", "enhanced"):
        typer.echo(f"--mode must be 'baseline' or 'enhanced', got {mode!r}")
        raise typer.Exit(code=1)

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

    scored_override = None
    if mode == "enhanced":
        scored_override = _build_enhanced_scores(settings, players, gameweek)

    squad = build_squad(players, budget=budget, scored_override=scored_override)

    captured_at = envelope["captured_at"]
    typer.echo(f"[{mode.upper()} MODEL — GW{gameweek}] captured_at={captured_at}")
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


def _build_enhanced_scores(
    settings: Settings, players: list[Player], gameweek: int
) -> list[ScoredPlayer]:
    """Assemble enhanced-mode scores: fixture difficulty (from the fixtures
    snapshot) layered with a history-based cold-start prior (from the
    element-history snapshot, optional). Missing either snapshot degrades
    gracefully — a missing fixtures snapshot falls back to a neutral
    multiplier for every team (not a silent 0, which would zero every
    score); a missing history snapshot just means no players get a prior,
    same as if none of them needed one.
    """
    from fpl_engine.baseline.fixture_signal import (
        fixture_score_multiplier,
        team_difficulties_for_gameweek,
    )
    from fpl_engine.baseline.historical_prior import historical_prior_score
    from fpl_engine.baseline.scoring import score_players_enhanced
    from fpl_engine.data.contracts import parse_element_history
    from fpl_engine.data.snapshot import read_latest_snapshot_any_season
    from fpl_engine.domain.models import Fixture

    team_ids = {p.team_id for p in players}

    fixture_multipliers: dict[int, float] = {}
    try:
        fixtures_envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_fixtures", gameweek=gameweek
        )
        raw_fixtures = [
            Fixture.from_raw_fixture(f) for f in fixtures_envelope["payload"]["fixtures"]
        ]
        for team_id in team_ids:
            diffs = team_difficulties_for_gameweek(raw_fixtures, team_id, gameweek)
            fixture_multipliers[team_id] = fixture_score_multiplier(diffs)
    except FileNotFoundError:
        typer.echo(
            f"  (no fixtures snapshot for GW{gameweek} — fixture difficulty "
            f"skipped this run; falling back to neutral for every team)"
        )
        fixture_multipliers = dict.fromkeys(team_ids, 1.0)

    historical_priors: dict[int, float] = {}
    try:
        history_envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_element_history", gameweek=gameweek
        )
        player_histories = history_envelope["payload"]["player_histories"]
        for pid_str, raw_history in player_histories.items():
            parsed = parse_element_history(int(pid_str), raw_history)
            prior = historical_prior_score(parsed.past_seasons)
            if prior is not None:
                historical_priors[int(pid_str)] = prior
    except FileNotFoundError:
        typer.echo(
            f"  (no element-history snapshot for GW{gameweek} — historical "
            f"priors skipped this run; run `fpl ingest-history --gameweek "
            f"{gameweek}` to enable them)"
        )

    return score_players_enhanced(players, fixture_multipliers, historical_priors)


@app.command("ingest-history")
def ingest_history(
    gameweek: int = typer.Option(..., help="Gameweek this snapshot is captured ahead of."),
    limit: int | None = typer.Option(
        None, help="Optional cap on number of players to fetch — useful while testing."
    ),
) -> None:
    """Pull per-player gameweek history (element-summary) for every player
    in the latest bootstrap snapshot.

    Sequential, one request per player (~600 requests) — deliberately
    simple for now; batching/concurrency is a Phase 19 (production
    hardening) concern, not something to add before it's needed. Expect
    this to take a while. `current_season` history will be EMPTY for any
    gameweek that hasn't been played yet — that's correct, not a bug; see
    docs/architecture.md Sec 18 on why real per-gameweek data can only
    accumulate one gameweek at a time.
    """
    from fpl_engine.data.fpl_client import FplClient
    from fpl_engine.data.snapshot import read_latest_snapshot_any_season, write_snapshot

    settings = get_settings()
    try:
        bootstrap_envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_bootstrap", gameweek=gameweek
        )
    except FileNotFoundError:
        typer.echo(
            f"No bootstrap snapshot for GW{gameweek}. "
            f"Run `fpl ingest --gameweek {gameweek}` first."
        )
        raise typer.Exit(code=1) from None

    bootstrap_payload = bootstrap_envelope["payload"]
    player_ids = [int(e["id"]) for e in bootstrap_payload["elements"]]
    if limit is not None:
        player_ids = player_ids[:limit]

    histories: dict[str, object] = {}
    with FplClient() as client:
        for i, player_id in enumerate(player_ids, start=1):
            histories[str(player_id)] = client.fetch_element_summary(player_id)
            if i % 50 == 0 or i == len(player_ids):
                typer.echo(f"  fetched {i}/{len(player_ids)} player histories...")

    season = _current_season_label(bootstrap_payload)
    path = write_snapshot(
        raw_dir=settings.raw_dir,
        source="fpl_element_history",
        season=season,
        gameweek=gameweek,
        payload={"player_histories": histories},
    )
    typer.echo(f"element history snapshot : {path}")
    typer.echo(f"players fetched           : {len(histories)}")


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
