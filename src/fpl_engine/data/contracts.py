"""Data contracts and validation at the raw -> staging boundary.

Per architecture.md Sec 4/6: this is the one place malformed or
unexpected-shape data from the FPL API gets caught, before it can reach
the feature engine or optimizer. One bad record should produce a
reportable issue, not a crashed pipeline or (worse) silently-wrong
downstream data — so parsing here is best-effort-with-reporting, not
all-or-nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fpl_engine.domain.models import Fixture, GameweekEvent, Player, Team

REQUIRED_BOOTSTRAP_KEYS = {"elements", "teams", "events"}


@dataclass
class ValidationIssue:
    entity: str  # "bootstrap", "player", "team", "event", "fixture"
    identifier: str  # e.g. player id, or "<payload>" for structural issues
    message: str


@dataclass
class ParsedBootstrap:
    players: list[Player] = field(default_factory=list)
    teams: list[Team] = field(default_factory=list)
    events: list[GameweekEvent] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0


def validate_bootstrap_shape(raw: dict[str, Any]) -> list[ValidationIssue]:
    """Structural check: are the top-level keys we depend on present at all?

    This runs before any per-record parsing — if this fails, the payload
    shape has likely changed upstream and per-record parsing isn't
    meaningful yet.
    """
    missing = REQUIRED_BOOTSTRAP_KEYS - raw.keys()
    if not missing:
        return []
    return [
        ValidationIssue(
            entity="bootstrap",
            identifier="<payload>",
            message=f"missing required top-level keys: {sorted(missing)}",
        )
    ]


def parse_bootstrap(raw: dict[str, Any]) -> ParsedBootstrap:
    """Parse a raw bootstrap-static payload into validated domain entities.

    Every record that fails to parse is recorded as an issue and skipped —
    it does not abort parsing of the rest of the payload. Callers decide
    whether `issues` is acceptable (e.g. a handful of malformed players)
    or should block the pipeline (e.g. `validate_bootstrap_shape` failing).
    """
    result = ParsedBootstrap()

    shape_issues = validate_bootstrap_shape(raw)
    if shape_issues:
        result.issues.extend(shape_issues)
        return result

    for raw_player in raw["elements"]:
        try:
            result.players.append(Player.from_bootstrap_element(raw_player))
        except (KeyError, ValueError, TypeError) as exc:
            result.issues.append(
                ValidationIssue(
                    entity="player",
                    identifier=str(raw_player.get("id", "<unknown>")),
                    message=str(exc),
                )
            )

    for raw_team in raw["teams"]:
        try:
            result.teams.append(Team.from_bootstrap_team(raw_team))
        except (KeyError, ValueError, TypeError) as exc:
            result.issues.append(
                ValidationIssue(
                    entity="team",
                    identifier=str(raw_team.get("id", "<unknown>")),
                    message=str(exc),
                )
            )

    for raw_event in raw["events"]:
        try:
            result.events.append(GameweekEvent.from_bootstrap_event(raw_event))
        except (KeyError, ValueError, TypeError) as exc:
            result.issues.append(
                ValidationIssue(
                    entity="event",
                    identifier=str(raw_event.get("id", "<unknown>")),
                    message=str(exc),
                )
            )

    return result


@dataclass
class ParsedFixtures:
    fixtures: list[Fixture] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0


def parse_fixtures(raw: list[dict[str, Any]]) -> ParsedFixtures:
    """Parse a raw /fixtures/ payload into validated Fixture entities."""
    result = ParsedFixtures()
    for raw_fixture in raw:
        try:
            result.fixtures.append(Fixture.from_raw_fixture(raw_fixture))
        except (KeyError, ValueError, TypeError) as exc:
            result.issues.append(
                ValidationIssue(
                    entity="fixture",
                    identifier=str(raw_fixture.get("id", "<unknown>")),
                    message=str(exc),
                )
            )
    return result


def cross_check_referential_integrity(parsed: ParsedBootstrap) -> list[ValidationIssue]:
    """Every player's team_id must reference a team that actually exists.

    Catches the case where bootstrap-static's `elements` and `teams` arrays
    have silently drifted out of sync (e.g. a partial/paginated fetch) —
    a structural problem the per-record parsers above can't see, since
    each record parses fine on its own.
    """
    known_team_ids = {t.id for t in parsed.teams}
    issues: list[ValidationIssue] = []
    for player in parsed.players:
        if player.team_id not in known_team_ids:
            issues.append(
                ValidationIssue(
                    entity="player",
                    identifier=str(player.id),
                    message=f"references unknown team_id={player.team_id}",
                )
            )
    return issues
