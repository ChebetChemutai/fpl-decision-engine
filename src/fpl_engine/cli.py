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


@app.command("chip-status")
def chip_status(
    gameweek: int = typer.Option(..., help="Gameweek to check chip legality for."),
) -> None:
    """Show, for each of the 4 chips, whether it's eligible this gameweek
    and whether you've already used it in the relevant half-season window.

    Chip rules come entirely from domain/chips.py — this command only
    reads and displays; it duplicates none of the eligibility logic.
    """
    from fpl_engine.data.state import read_chip_state
    from fpl_engine.domain.chips import Chip, is_gameweek_eligible, window_for_gameweek

    settings = get_settings()
    state = read_chip_state(settings.data_dir)

    typer.echo(f"Chip status for GW{gameweek}:")
    for chip in Chip:
        if not is_gameweek_eligible(chip, gameweek):
            typer.echo(f"  {chip.value:<15} not eligible this gameweek")
            continue
        window = window_for_gameweek(chip, gameweek)
        available = state.is_available(chip, window=window)
        status = "available" if available else f"already used ({window.value})"
        typer.echo(f"  {chip.value:<15} {status}")


@app.command("chip-play")
def chip_play(
    chip: str = typer.Option(..., help="wildcard | free_hit | bench_boost | triple_captain"),
    gameweek: int = typer.Option(..., help="Gameweek to play the chip in."),
) -> None:
    """Record a chip as played for this gameweek. Validates legality
    entirely through domain/chips.py::ChipState.play — this command does
    not re-implement or duplicate the eligibility/window rules.
    """
    from fpl_engine.data.state import read_chip_state, write_chip_state
    from fpl_engine.domain.chips import Chip

    try:
        chip_enum = Chip(chip)
    except ValueError:
        valid = ", ".join(c.value for c in Chip)
        typer.echo(f"'{chip}' is not a valid chip. Valid options: {valid}")
        raise typer.Exit(code=1) from None

    settings = get_settings()
    state = read_chip_state(settings.data_dir)
    try:
        updated = state.play(chip_enum, gameweek)
    except ValueError as exc:
        typer.echo(f"Cannot play {chip}: {exc}")
        raise typer.Exit(code=1) from None

    write_chip_state(settings.data_dir, updated)
    typer.echo(f"Recorded: {chip} played in GW{gameweek}.")


@app.command("transfer-check")
def transfer_check(
    gameweek: int = typer.Option(..., help="Gameweek the current squad's prices are from."),
    current: list[int] = typer.Option(  # noqa: B008
        ..., help="Player IDs of your current 15-man squad."
    ),
    out_ids: list[int] = typer.Option(  # noqa: B008
        ..., "--out", help="Player ID(s) to transfer out."
    ),
    in_ids: list[int] = typer.Option(  # noqa: B008
        ..., "--in", help="Player ID(s) to transfer in."
    ),
    free_transfers: int = typer.Option(1, help="Free transfers available this gameweek."),
) -> None:
    """Validate a candidate transfer (or set of transfers) against the
    domain rules and report the resulting squad's legality and cost.

    This is validation only — no search, no recommendation of WHICH
    transfer to make (integration spec Sec 9: that's a future transfer
    optimizer's job, not this command's).
    """
    from fpl_engine.data.snapshot import read_latest_snapshot_any_season
    from fpl_engine.domain.models import Player
    from fpl_engine.domain.rules import validate_squad
    from fpl_engine.domain.transfers import calculate_transfer_cost

    if len(out_ids) != len(in_ids):
        typer.echo(
            f"--out and --in must have the same count "
            f"(got {len(out_ids)} out, {len(in_ids)} in)."
        )
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

    all_players = {
        int(e["id"]): Player.from_bootstrap_element(e) for e in envelope["payload"]["elements"]
    }

    missing = [pid for pid in [*current, *out_ids, *in_ids] if pid not in all_players]
    if missing:
        typer.echo(f"Unknown player ID(s) in this snapshot: {missing}")
        raise typer.Exit(code=1)

    if set(out_ids) - set(current):
        missing_out = set(out_ids) - set(current)
        typer.echo(f"Cannot transfer out player(s) not in --current: {missing_out}")
        raise typer.Exit(code=1)

    resulting_ids = [pid for pid in current if pid not in out_ids] + list(in_ids)
    resulting_squad = [all_players[pid] for pid in resulting_ids]

    unavailable_statuses = ("i", "s", "u", "n")
    unavailable_incoming = [
        p.web_name
        for p in resulting_squad
        if p.id in in_ids and p.status.value in unavailable_statuses
    ]
    if unavailable_incoming:
        typer.echo(f"Warning: incoming player(s) currently unavailable: {unavailable_incoming}")

    violations = validate_squad(resulting_squad)
    cost = calculate_transfer_cost(len(out_ids), free_transfers)

    typer.echo(f"Transfers: {len(out_ids)} out, {len(in_ids)} in")
    typer.echo(f"Cost: {cost} points ({free_transfers} free transfer(s) available)")
    if violations:
        typer.echo("Resulting squad is ILLEGAL:")
        for v in violations:
            typer.echo(f"  - {v}")
        raise typer.Exit(code=1)
    typer.echo("Resulting squad is LEGAL.")


@app.command("backtest")
def backtest(
    gameweek: int = typer.Option(..., help="Gameweek to evaluate against real results."),
) -> None:
    """Run a REAL historical evaluation for `gameweek`, using whatever
    per-player results `fpl ingest-history` has actually captured.

    This is NOT a demo with invented numbers — if no player has a real
    recorded result for this gameweek yet, that's reported plainly as
    zero cases, not papered over with a fake-looking metric. See
    docs/architecture.md Sec 7/8/12 and the integration spec's explicit
    instruction not to fabricate historical results.
    """
    from fpl_engine.data.contracts import parse_element_history
    from fpl_engine.data.snapshot import read_latest_snapshot_any_season
    from fpl_engine.domain.models import Player
    from fpl_engine.models.backtest import run_backtest
    from fpl_engine.models.baselines import FormWeightedBaseline, PositionAverageBaseline
    from fpl_engine.models.data_pipeline import (
        build_backtest_cases,
        build_training_points_by_position,
    )

    settings = get_settings()
    try:
        bootstrap_envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_bootstrap", gameweek=gameweek
        )
        history_envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_element_history", gameweek=gameweek
        )
    except FileNotFoundError as exc:
        typer.echo(f"Missing snapshot: {exc}")
        typer.echo(
            f"Need both `fpl ingest --gameweek {gameweek}` and "
            f"`fpl ingest-history --gameweek {gameweek}` first."
        )
        raise typer.Exit(code=1) from None

    elements = bootstrap_envelope["payload"]["elements"]
    positions_by_player = {
        int(e["id"]): Player.from_bootstrap_element(e).position for e in elements
    }

    player_histories = {}
    for pid_str, raw_history in history_envelope["payload"]["player_histories"].items():
        parsed = parse_element_history(int(pid_str), raw_history)
        player_histories[int(pid_str)] = parsed.current_season

    cases = build_backtest_cases(player_histories, positions_by_player, target_gameweek=gameweek)

    if not cases:
        typer.echo(f"REAL HISTORICAL EVALUATION — GW{gameweek}: 0 cases.")
        typer.echo(
            f"No player has a recorded result for GW{gameweek} yet — this gameweek "
            f"hasn't been played, or `fpl ingest-history` was run before it finished. "
            f"This is the correct, honest output when there's nothing real to evaluate "
            f"yet; it is not an error."
        )
        return

    training = build_training_points_by_position(
        player_histories, positions_by_player, before_gameweek=gameweek
    )
    position_avg_model = PositionAverageBaseline.fit(training)
    form_model = FormWeightedBaseline(position_avg_model)

    position_avg_result = run_backtest(position_avg_model, cases)
    form_result = run_backtest(form_model, cases)

    typer.echo(f"REAL HISTORICAL EVALUATION — GW{gameweek}: {len(cases)} case(s)")
    pos_avg_mae, pos_avg_rmse = position_avg_result.mae, position_avg_result.rmse
    typer.echo(f"  PositionAverageBaseline:  MAE={pos_avg_mae}  RMSE={pos_avg_rmse}")
    typer.echo(f"  FormWeightedBaseline:     MAE={form_result.mae}  RMSE={form_result.rmse}")
    if form_result.mae < position_avg_result.mae:
        typer.echo("  -> FormWeightedBaseline beat the naive baseline on this real data.")
    else:
        typer.echo("  -> FormWeightedBaseline did NOT beat the naive baseline on this real data.")


manager_app = typer.Typer(
    help="Read-only manager (entry) account commands. See docs/manager-integration.md."
)
app.add_typer(manager_app, name="manager")


@manager_app.command("status")
def manager_status(manager_id: int = typer.Option(..., help="Your FPL manager/entry ID.")) -> None:
    """Print public profile info for a manager. Read-only — never writes
    to your FPL account (architecture.md Sec 29). No authentication is
    attempted; if this fails with an auth error, see
    docs/manager-integration.md for what's actually confirmed public.
    """
    from fpl_engine.data.fpl_client import FplClient
    from fpl_engine.domain.manager import ManagerProfile

    with FplClient() as client:
        raw = client.fetch_manager_entry(manager_id)
    profile = ManagerProfile.from_raw(raw)

    typer.echo(f"{profile.player_first_name} {profile.player_last_name} — {profile.team_name}")
    typer.echo(f"Overall points: {profile.summary_overall_points}")
    typer.echo(f"Overall rank:   {profile.summary_overall_rank}")
    typer.echo(f"Current GW:     {profile.current_event}")


@manager_app.command("history")
def manager_history(manager_id: int = typer.Option(..., help="Your FPL manager/entry ID.")) -> None:
    """Print this-season gameweek-by-gameweek history for a manager."""
    from fpl_engine.data.contracts import parse_manager_history
    from fpl_engine.data.fpl_client import FplClient

    with FplClient() as client:
        raw = client.fetch_manager_history(manager_id)
    parsed = parse_manager_history(manager_id, raw)

    if not parsed.is_clean:
        typer.echo(f"Warning: {len(parsed.issues)} gameweek(s) could not be parsed.")
    for gw in parsed.gameweeks:
        typer.echo(
            f"GW{gw.event:<3} pts={gw.points:<4} total={gw.total_points:<5} "
            f"rank={gw.rank} overall_rank={gw.overall_rank} "
            f"bank={gw.bank / 10:.1f}m value={gw.value / 10:.1f}m "
            f"transfers={gw.event_transfers} (cost {gw.event_transfers_cost})"
        )


@manager_app.command("picks")
def manager_picks(
    manager_id: int = typer.Option(..., help="Your FPL manager/entry ID."),
    gameweek: int = typer.Option(..., help="Gameweek to fetch picks for."),
) -> None:
    """Print a manager's squad picks for a gameweek.

    Whether this works for the CURRENT (unfinished) gameweek without
    authentication is genuinely unconfirmed — see
    docs/manager-integration.md. Past-gameweek picks are documented as
    public. An auth error here is surfaced as-is, not worked around.
    """
    from fpl_engine.data.contracts import parse_manager_picks
    from fpl_engine.data.fpl_client import FplClient

    with FplClient() as client:
        raw = client.fetch_manager_picks(manager_id, gameweek)
    parsed = parse_manager_picks(manager_id, gameweek, raw)

    if not parsed.is_clean:
        typer.echo(f"Warning: {len(parsed.issues)} pick(s) could not be parsed.")
    typer.echo(f"Active chip: {parsed.active_chip or 'none'}")
    for pick in sorted(parsed.picks, key=lambda p: p.position):
        marker = " (C)" if pick.is_captain else " (VC)" if pick.is_vice_captain else ""
        bench_note = " [bench]" if pick.position > 11 else ""
        typer.echo(f"  slot {pick.position:>2}: element {pick.element}{marker}{bench_note}")


@manager_app.command("evaluate")
def manager_evaluate(
    manager_id: int = typer.Option(..., help="Your FPL manager/entry ID."),
    gameweek: int = typer.Option(..., help="Gameweek to evaluate."),
) -> None:
    """Compare your actual submitted squad's real points to what the
    baseline model would have recommended, both scored against real
    results.

    The baseline is reconstructed from the EARLIEST ingested bootstrap
    snapshot for this gameweek — the one closest to what would have
    been recommended before the deadline — never a fresh fetch, since
    ep_next changes over time and a fresh fetch today would not
    represent what the tool actually said back then.

    Does not model automatic substitutions on either side — see
    models/evaluation.py's module docstring.
    """
    from fpl_engine.baseline.squad_builder import build_squad
    from fpl_engine.data.contracts import parse_element_history, parse_manager_picks
    from fpl_engine.data.fpl_client import FplClient
    from fpl_engine.data.snapshot import (
        read_earliest_snapshot_any_season,
        read_latest_snapshot_any_season,
    )
    from fpl_engine.domain.models import Player
    from fpl_engine.models.evaluation import (
        SquadPick,
        evaluate_squad_points,
        points_by_player_from_element_history,
        squad_to_picks,
    )

    settings = get_settings()
    try:
        bootstrap_envelope = read_earliest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_bootstrap", gameweek=gameweek
        )
    except FileNotFoundError:
        typer.echo(
            f"No bootstrap snapshot for GW{gameweek}. "
            f"Run `fpl ingest --gameweek {gameweek}` first."
        )
        raise typer.Exit(code=1) from None

    try:
        history_envelope = read_latest_snapshot_any_season(
            raw_dir=settings.raw_dir, source="fpl_element_history", gameweek=gameweek
        )
    except FileNotFoundError:
        typer.echo(
            f"No element-history snapshot for GW{gameweek}. "
            f"Run `fpl ingest-history --gameweek {gameweek}` first."
        )
        raise typer.Exit(code=1) from None

    players = [Player.from_bootstrap_element(e) for e in bootstrap_envelope["payload"]["elements"]]
    baseline_squad = build_squad(players)

    player_histories = {}
    for pid_str, raw_history in history_envelope["payload"]["player_histories"].items():
        parsed_history = parse_element_history(int(pid_str), raw_history)
        player_histories[int(pid_str)] = parsed_history.current_season
    points_by_player = points_by_player_from_element_history(player_histories, gameweek)

    with FplClient() as client:
        raw_picks = client.fetch_manager_picks(manager_id, gameweek)
    parsed_picks = parse_manager_picks(manager_id, gameweek, raw_picks)
    actual_picks = [
        SquadPick(player_id=p.element, multiplier=p.multiplier) for p in parsed_picks.picks
    ]

    actual_points = evaluate_squad_points(actual_picks, points_by_player)
    baseline_points = evaluate_squad_points(squad_to_picks(baseline_squad), points_by_player)

    typer.echo(f"GW{gameweek} evaluation — manager {manager_id}")
    typer.echo(f"  Actual submitted squad: {actual_points} points")
    typer.echo(
        f"  Baseline model squad:   {baseline_points} points "
        f"(reconstructed from snapshot captured {bootstrap_envelope['captured_at']})"
    )
    diff = actual_points - baseline_points
    if diff > 0:
        typer.echo(f"  You beat the baseline by {diff} points.")
    elif diff < 0:
        typer.echo(f"  The baseline would have beaten you by {-diff} points.")
    else:
        typer.echo("  Tied.")
    typer.echo(
        "  Note: automatic substitutions are not modeled on either side — "
        "treat a close result with caution if a starter didn't play."
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
