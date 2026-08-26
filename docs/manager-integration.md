# Manager (Entry) Integration — Status

## What's confirmed vs. documentation-only

**Update 2026-08-26**: the previously-open question is resolved.
`fpl manager status` and `fpl manager picks` were both run against a
real account (manager 6313636, GW1) on the user's own machine, and the
raw JSON response was captured directly via `curl`. Findings below are
now real-data-confirmed, not documentation-based guesses.

| Endpoint | Status |
|---|---|
| `GET /entry/{id}/` | **CONFIRMED with real data.** `ManagerProfile` parses it correctly. |
| `GET /entry/{id}/history/` | Core fields confirmed via the shared `entry_history` shape in the picks response (see below). Not independently fetched on its own yet, but the shape is the same object. |
| `GET /entry/{id}/event/{gw}/picks/` | **CONFIRMED with real data — fully public, no authentication needed**, at least for a gameweek that's been played. The "genuinely unresolved" auth question from earlier is settled. |
| `GET /entry/{id}/transfers/` | Client method exists (`fetch_manager_transfers`); still no parsing/CLI built — deferred. |

### Real response shape (picks endpoint), confirmed 2026-08-26

```json
{
  "active_chip": null,
  "automatic_subs": [],
  "entry_history": {
    "event": 1, "points": 59, "total_points": 59, "rank": 1987559,
    "rank_sort": 2138852, "overall_rank": 1987556, "percentile_rank": 25,
    "overall_rank_percentage": "22", "bank": 0, "value": 1000,
    "event_transfers": 0, "event_transfers_cost": 0, "points_on_bench": 10
  },
  "picks": [
    {
      "element": 1, "position": 1, "multiplier": 1,
      "is_captain": false, "is_vice_captain": true, "element_type": 1
    }
  ]
}
```

`ManagerPick` and `ManagerGameweekHistory` capture every field here
**except** `rank_sort`, `percentile_rank`, `overall_rank_percentage`,
and `automatic_subs` — all real and present, deliberately not parsed
yet since nothing currently needs them. Add on demand, not speculatively.

**Confirmed ABSENT**: `selling_price` and `purchase_price` do NOT
appear anywhere in this response. The earlier open question ("might
these exist?") is now answered: no, not in this endpoint, at least not
for an already-played gameweek. `ManagerPick` correctly does not include
them.

## What's deliberately NOT built yet

- **No authentication support at all**, and — now confirmed — none is
  needed for the endpoints this codebase uses. If a future endpoint
  (e.g. viewing an in-progress, not-yet-played gameweek's picks, or
  making transfers) does require it, that's still a separate,
  explicitly-scoped security project.
- **Not wired into scoring, optimization, or recommendations.**
  Intentional (spec Sec 13) — `fpl manager *` commands are read-only
  display today.
- **No league/classic-standings endpoints.** Documented to exist, not
  built this session.
- **`selling_price`/`purchase_price` tracking**: the domain-level
  selling-price *rule* is implemented and verified
  (`domain/pricing.py`) — but since the picks endpoint doesn't hand you
  a selling price directly, using it for a real squad means combining
  `purchase_price` from `/entry/{id}/transfers/` (not yet parsed) with
  current `now_cost` from bootstrap-static, and computing it ourselves.
  Deferred — needs the transfers endpoint parsed first.

## Commands available today

```bash
fpl manager status --manager-id <id>
fpl manager history --manager-id <id>
fpl manager picks --manager-id <id> --gameweek <n>
```

All read-only, all confirmed working against a real account. None send,
modify, or delete anything on the real FPL account.
