"""FPL data provider.

Talks to the official (unofficial-but-public) FPL API. Kept behind a small
interface — `FplClient` — so a future data source swap doesn't ripple into
ingestion/rules/optimizer code (architecture.md Sec 4).

Network note: this must be run somewhere that can reach
fantasy.premierleague.com. It is NOT reachable from this project's CI
sandbox network allowlist — run `fpl ingest` locally.
"""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://fantasy.premierleague.com/api"


class FplClient:
    """Thin, typed wrapper over the FPL public API. No caching, no retries yet
    — those are a Phase 3 (full data ingestion) concern, not Phase 1.5.
    """

    def __init__(self, base_url: str = BASE_URL, timeout: float = 15.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def fetch_bootstrap(self) -> dict[str, Any]:
        """GET /bootstrap-static/ — players, teams, events, game settings."""
        response = self._client.get("/bootstrap-static/")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def fetch_fixtures(self, event: int | None = None) -> list[dict[str, Any]]:
        """GET /fixtures/ — optionally filtered to a single gameweek."""
        params = {"event": event} if event is not None else None
        response = self._client.get("/fixtures/", params=params)
        response.raise_for_status()
        result: list[dict[str, Any]] = response.json()
        return result

    def fetch_element_summary(self, element_id: int) -> dict[str, Any]:
        """GET /element-summary/{element_id}/ — one player's per-gameweek
        history for the CURRENT season (`history`, empty until gameweeks
        have actually been played) and season-level totals for prior
        seasons (`history_past`, no per-gameweek breakdown available).
        """
        response = self._client.get(f"/element-summary/{element_id}/")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def fetch_manager_entry(self, manager_id: int) -> dict[str, Any]:
        """GET /entry/{manager_id}/ — public manager profile (name, team
        name, overall points/rank). Documented as unauthenticated/public
        by multiple independent sources; not independently live-fetch-
        verified in this codebase yet (see docs/manager-integration.md).
        """
        response = self._client.get(f"/entry/{manager_id}/")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def fetch_manager_history(self, manager_id: int) -> dict[str, Any]:
        """GET /entry/{manager_id}/history/ — this-season per-gameweek
        summary (points, rank, bank, value, transfers, chips used) plus
        prior-season season-level totals.
        """
        response = self._client.get(f"/entry/{manager_id}/history/")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def fetch_manager_picks(self, manager_id: int, event_id: int) -> dict[str, Any]:
        """GET /entry/{manager_id}/event/{event_id}/picks/ — that manager's
        15-man squad for a specific gameweek.

        Documentation sources disagree on whether this is public for the
        CURRENT (not-yet-finished) gameweek or requires authentication —
        genuinely unresolved in this codebase; see
        docs/manager-integration.md. Past-gameweek picks are documented
        as public. This method does not attempt to authenticate; a 401/403
        here should be surfaced to the caller as-is, not silently retried
        or worked around.
        """
        response = self._client.get(f"/entry/{manager_id}/event/{event_id}/picks/")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def fetch_manager_transfers(self, manager_id: int) -> list[dict[str, Any]]:
        """GET /entry/{manager_id}/transfers/ — full transfer history."""
        response = self._client.get(f"/entry/{manager_id}/transfers/")
        response.raise_for_status()
        result: list[dict[str, Any]] = response.json()
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FplClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
