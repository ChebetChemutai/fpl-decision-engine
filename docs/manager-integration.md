# Manager (Entry) Integration — Status

## What's confirmed vs. documentation-only

Unlike `bootstrap-static`, `fixtures`, and `element-summary` — all
independently confirmed this session via live fetches against the real
2026/27 API — the manager (`/entry/`) endpoints below are implemented
against **published third-party documentation only**. Multiple
independent sources agree on these field names, but this codebase has
not yet made a live call against a real account to confirm them.

| Endpoint | Status |
|---|---|
| `GET /entry/{id}/` | Documentation-based. Widely described as public/unauthenticated. |
| `GET /entry/{id}/history/` | Documentation-based. Widely described as public/unauthenticated. |
| `GET /entry/{id}/event/{gw}/picks/` | **Genuinely unresolved.** Sources disagree on whether the *current, unfinished* gameweek's picks require authentication (to stop rivals seeing your team before the deadline) or are public like past gameweeks. |
| `GET /entry/{id}/transfers/` | Client method exists (`fetch_manager_transfers`); no parsing/CLI built yet — deferred. |

**Action before trusting this in production:** run
`fpl manager status --manager-id <a real id>` against a real ID once,
inspect the raw response, and confirm the field names in
`domain/manager.py` match exactly. Extend the models (e.g. add
`selling_price`/`purchase_price` to `ManagerPick` if the real `picks`
response actually includes them — several sources hint it might, but
none gave an exact field name confidently enough to encode without
guessing).

## What's deliberately NOT built yet

- **No authentication support at all.** No password, session cookie, or
  token handling exists anywhere in this codebase, by design
  (architecture.md Sec 29, and this session's spec Sec 12). If
  `manager picks` for the current gameweek turns out to require auth,
  that's a separate, explicitly-scoped security project — not a gap to
  quietly patch around.
- **Not wired into scoring, optimization, or recommendations.** This is
  intentional, matching the spec's own Section 13: "First establish
  correct manager state" before connecting it deeper. `fpl manager *`
  commands are read-only display today — they don't feed `fpl squad`,
  `fpl transfer-check`, or anything else.
- **No league/classic-standings endpoints implemented.** Documented to
  exist (`/leagues-classic/{id}/standings/`, paginated), but not built
  this session — correctly deferred per the spec's own instruction not
  to build competitor analytics before basic manager integration works.
- **`selling_price`/`purchase_price` per pick are NOT in `ManagerPick`.**
  The domain-level selling-price *rule* is implemented and verified
  (`domain/pricing.py`) — but whether the real picks endpoint hands you
  a pre-computed selling price per player, or you're expected to derive
  it yourself from `purchase_price` + current `now_cost`, is unconfirmed.
  Don't guess the field name; confirm it against a real response first.

## Commands available today

```bash
fpl manager status --manager-id <id>
fpl manager history --manager-id <id>
fpl manager picks --manager-id <id> --gameweek <n>
```

All read-only. None of these send, modify, or delete anything on the
real FPL account.
