"""Local application state — currently just chip usage.

Deliberately separate from `data/raw/` (architecture.md Sec 28: never mix
raw ingested data with application state). There is no FPL account
integration (by design — see docs/architecture.md Sec 29), so chip usage
has nowhere authoritative to live except locally; this file is that
manager's own record of what they've played, kept in sync manually.
"""

from __future__ import annotations

from pathlib import Path

from fpl_engine.domain.chips import ChipState


def _state_path(data_dir: Path) -> Path:
    return data_dir / "state" / "chips.json"


def read_chip_state(data_dir: Path) -> ChipState:
    """Returns a fresh (no chips used) state if nothing has been recorded
    yet — a missing state file is a legitimate starting point, not an error.
    """
    path = _state_path(data_dir)
    if not path.exists():
        return ChipState()
    return ChipState.model_validate_json(path.read_text(encoding="utf-8"))


def write_chip_state(data_dir: Path, state: ChipState) -> Path:
    path = _state_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path
