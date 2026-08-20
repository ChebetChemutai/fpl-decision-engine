"""Raw data snapshot writer.

Every ingestion run writes a new, timestamped, immutable file — never
overwrites a prior snapshot. This is what makes "what did we know as of
GW N's deadline" answerable later, and it's a hard architectural rule, not
a style choice (architecture.md Sec 4 and Sec 6).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def write_snapshot(
    *,
    raw_dir: Path,
    source: str,
    season: str,
    gameweek: int,
    payload: dict[str, Any],
) -> Path:
    """Write a raw snapshot and return the path it was written to.

    Layout: {raw_dir}/{source}/{season}/{gameweek}/{timestamp}.json
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target_dir = raw_dir / source / season / str(gameweek)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{timestamp}.json"

    envelope = {
        "source": source,
        "season": season,
        "gameweek": gameweek,
        "schema_version": SCHEMA_VERSION,
        "captured_at": timestamp,
        "payload": payload,
    }
    target_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return target_path


def read_latest_snapshot(
    *, raw_dir: Path, source: str, season: str, gameweek: int
) -> dict[str, Any]:
    """Read the most recently written snapshot for a given source/season/GW."""
    target_dir = raw_dir / source / season / str(gameweek)
    snapshots = sorted(target_dir.glob("*.json"))
    if not snapshots:
        raise FileNotFoundError(f"no snapshots found in {target_dir}")
    data: dict[str, Any] = json.loads(snapshots[-1].read_text(encoding="utf-8"))
    return data


def read_latest_snapshot_any_season(*, raw_dir: Path, source: str, gameweek: int) -> dict[str, Any]:
    """Read the most recently written snapshot for a source/GW, searching
    across all season directories. Convenience for callers (like the CLI)
    that know the gameweek but not the season label a prior `ingest` run
    derived.
    """
    candidates = sorted((raw_dir / source).glob(f"*/{gameweek}/*.json"))
    if not candidates:
        raise FileNotFoundError(
            f"no snapshots found for source={source!r} gameweek={gameweek} under {raw_dir}"
        )
    data: dict[str, Any] = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return data
