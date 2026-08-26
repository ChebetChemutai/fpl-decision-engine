# Phases 1–5 Consolidation Audit — Final Report

**Update 2026-08-26**: the manager-picks field-shape question (the
single largest open item below) is now resolved against real data —
see Section 25. Still not declaring full "READY FOR PHASE 6" in this
update, since league data and the GW1-actual-vs-baseline comparison
remain unbuilt, but the foundation is materially stronger than the
original version of this report.

**Original verdict, for context: NOT declaring "PHASES 1–5 COMPLETE
AND VERIFIED — READY FOR PHASE 6" yet.** Real progress was made this
session, but items in the spec's own acceptance criteria were
genuinely incomplete — see Section 25 below.

---

## 1–2. Audit findings / disconnected components

Grep-verified at the start of this session (not recalled from memory):

| Capability | State found |
|---|---|
| Fixture difficulty, history_past, chips, transfers, temporal features, backtesting | **Genuinely integrated** — confirmed by grep showing actual call sites in `cli.py`, not just imports. This matches the prior session's report and had not regressed. |
| Manager/account layer | **Did not exist at all.** No `entry` endpoints, no manager domain models, nothing in `cli.py`. |
| Price / selling-value logic | **Did not exist at all.** No `selling_price`, `purchase_price`, or `sell_price` anywhere in the codebase. |
| PuLP deprecation warnings | Already fixed in a prior commit (`c0ceed3`); re-verified this session by rerunning the suite with `-W error::DeprecationWarning` — clean. |
| CLI coverage | 94% overall as of this session's end (was 91% before this session's additions). |

## 3. What was integrated this session

- `domain/pricing.py::calculate_selling_price` — new capability, unit-tested against 6 independently-sourced worked examples, not wired into anything yet (it's a pure function; nothing in this codebase currently tracks a manager's actual purchase prices to call it against — see Section 25).
- `domain/manager.py`, `data/fpl_client.py` (4 new methods), `data/contracts.py` (2 new parse functions), `cli.py` (`fpl manager status|history|picks`) — new manager read layer, explicitly NOT wired into scoring/recommendations (matches spec Sec 13's own sequencing).

## 4–5. Files changed / added

**Added:** `domain/pricing.py`, `domain/manager.py`, `docs/manager-integration.md`, `docs/final-phase-1-5-audit.md` (this file), `tests/test_pricing.py`, `tests/test_manager.py`.

**Changed:** `data/fpl_client.py` (+4 methods), `data/contracts.py` (+2 parse functions, +1 import line), `cli.py` (+3 commands under a new `manager` sub-app), `tests/test_cli_integration.py` (+4 manager CLI tests).

**Removed:** nothing.

## 6. Database migrations

None. This project has no database — file-based snapshots and local JSON state only (architecture.md Sec 28, `data/state.py`). No change needed.

## 7. API endpoints used

`GET /entry/{id}/`, `GET /entry/{id}/history/`, `GET /entry/{id}/event/{gw}/picks/`, `GET /entry/{id}/transfers/` (client method exists, unused beyond that). All GET, all read-only, no authentication.

## 8. Manager/account architecture

`FplClient` extended with manager methods alongside its existing global-data methods (single client, conceptually separated by method naming — `fetch_manager_*` vs `fetch_bootstrap`/`fetch_fixtures`/`fetch_element_summary`). `ManagerProfile`, `ManagerGameweekHistory`, `ManagerPick` in `domain/manager.py`. Deliberately minimal field sets — see `docs/manager-integration.md` for exactly what's confirmed vs. documentation-only.

## 9. Price/team-value architecture

`domain/pricing.py::calculate_selling_price(purchase_cost, now_cost) -> int`, in FPL's native tenths-of-a-million integer units. Implements the verified official rule (half profit rounded down; full loss on a fall). Team value / bank tracking exists at the data level (`ManagerGameweekHistory.bank`/`.value`) but no aggregation logic sits on top of it yet — correctly deferred, since it needs real squad+price data to be meaningful, which needs the still-open manager-picks question resolved first.

## 10. Fixture integration

Unchanged from the prior session — still genuinely connected (`fixture_score_multiplier`/`team_difficulties_for_gameweek` called from `cli.py::_build_enhanced_scores`). Re-verified by grep this session, not just carried over as a claim.

## 11. Historical integration

Unchanged from prior sessions. `parse_element_history` → `GameweekPerformance` (now carrying the full real stat set, extended two sessions ago) → `compute_features`/`build_backtest_cases`, all still genuinely wired.

## 12. Temporal leakage protections

Unchanged and re-verified: `compute_features` filters to `gameweek < target_gameweek` internally regardless of what the caller passes; `build_backtest_cases`/`build_training_points_by_position` apply the same discipline to backtest case construction and baseline fitting respectively. No new leakage surface was introduced this session — `pricing.py` and `manager.py` are both pure/data-shape code with no temporal dimension of their own yet (a manager's current squad isn't a time-series input to anything).

## 13. Backtesting integration

Unchanged from the prior session. `fpl backtest --gameweek N` still correctly reports 0 real cases as of this session (see Section 24 — GW2 hasn't been ingested).

## 14. Chip integration

Unchanged. `fpl chip-status`/`fpl chip-play` still genuinely call into `domain/chips.py`. Not extended to read real manager chip usage this session — `fetch_manager_history`'s response is documented to include chip usage, but connecting it to `data/state.py`'s local `ChipState` was not attempted this session (would need the manager-picks question resolved first, to avoid building on an unconfirmed field shape).

## 15. Transfer integration

Unchanged. `fpl transfer-check` still validates candidate transfers against `domain/transfers.py`. Not connected to a manager's real current squad this session — same reasoning as chips above.

## 16. CLI changes

Added `fpl manager status --manager-id <id>`, `fpl manager history --manager-id <id>`, `fpl manager picks --manager-id <id> --gameweek <n>`, as a new `manager` sub-command group (`typer.Typer` sub-app), consistent with the existing CLI's structure — no second CLI framework introduced.

## 17. PuLP migration

No new work this session; re-verified the prior fix still holds (`pytest -W error::DeprecationWarning` passes clean, 0 warnings).

## 18. Tests added

21 new this session: 9 for `pricing.py` (every documented rule example, plus a large-rise and large-fall edge case), 8 for manager parsing (`ManagerProfile`, `ManagerGameweekHistory`, `ManagerPick`, both clean and malformed-entry cases), 4 CLI-level for the three manager commands (mocked `FplClient` — none touch the live API).

## 19. Final test count

**191** (170 before this session).

## 20–22. pytest / ruff / mypy results

```
191 passed in 3.16s
ruff: All checks passed!
mypy --strict: Success: no issues found in 30 source files
```

## 23. Real FPL data verification result

- **Pricing rule**: verified against 6 independent documentation sources with matching worked examples — not a live API fetch (selling price isn't raw ingested data, it's a domain calculation), but the *rule itself* is confirmed, not guessed.
- **Manager endpoints**: **NOT verified with real FPL data this session.** Every manager-related model and parser is built against third-party documentation only. This is the most important honesty flag in this report — see `docs/manager-integration.md`.
- Everything from prior sessions (bootstrap-static, fixtures, element-summary, GW1 scoring validation) remains real-data-verified as previously reported; nothing in that set was touched or re-broken this session.

## 24. GW1 evaluation result

**Not run this session.** The spec's Section 14 (AI baseline vs. actual submitted team vs. actual result) needs a real manager ID to fetch actual GW1 picks and history against — that's the user's real account, which I don't have an ID for and wouldn't fetch without it being given. `fpl backtest --gameweek 1` (the separate, already-built real-data backtest) still reports 0 cases as of this report, since GW2 (needed to have a target gameweek with a completed predecessor to backtest against under the current design) hasn't been ingested yet either.

## 25. Known limitations (unresolved from the spec's acceptance criteria)

- ~~Manager `picks` field shapes are unconfirmed~~ **RESOLVED 2026-08-26**:
  confirmed against a real account (manager 6313636, GW1). Fully public,
  no authentication needed. `ManagerPick` extended with the one real
  field it was missing (`element_type`); confirmed `selling_price`/
  `purchase_price` genuinely do not appear in this endpoint.
- **League/classic-standings endpoints are not implemented** — documented to exist, deliberately deferred per the spec's own "don't build competitor analytics before basic manager integration works" instruction (Section 25).
- **Official 2026/27 Price Change Predictor**: confirmed to exist and be real (multiple sources), and its likely underlying data (`price_change_percent`, `price_change_projections`) was already confirmed present in a live bootstrap-static fetch two sessions ago — but no dedicated parsing/exposure of these fields was built this session; they currently pass through unused in the raw snapshot.
- **Manager data does not reach the recommendation layer** — by design, per spec Sec 13's sequencing, not an oversight.
- **GW1 actual-vs-baseline comparison** — now unblocked (a real manager ID exists), but not yet run — the comparison logic itself (squad vs squad, points vs points) hasn't been built.
- **Selling price can't be computed for a real squad yet** — the rule is verified, but applying it needs `purchase_price` from `/entry/{id}/transfers/`, which is fetched but not parsed.

## 26. Components deliberately deferred to Phase 6+

Everything the spec itself listed in Section 41: competitor simulator, Monte Carlo league simulator, advanced transfer optimizer, price-prediction ML model, strategic chip optimizer, automated retraining. None of these were touched, correctly.

## 27. Exact commands

```bash
# Sync global FPL data
fpl ingest --gameweek <N>
fpl ingest-history --gameweek <N>

# Manager account (read-only; verify field shapes against your real ID first)
fpl manager status --manager-id <your-id>
fpl manager history --manager-id <your-id>
fpl manager picks --manager-id <your-id> --gameweek <N>

# Recommendation
fpl squad --gameweek <N>              # enhanced mode
fpl squad --gameweek <N> --mode baseline

# Evaluation
fpl backtest --gameweek <N>
```

---

## Summary: IMPLEMENTED vs VERIFIED

| | Implemented | Unit tested | Integration tested | Verified w/ real data |
|---|---|---|---|---|
| Fixture difficulty | ✅ | ✅ | ✅ | ✅ (prior session) |
| History_past prior | ✅ | ✅ | ✅ | ✅ (prior session) |
| Chips | ✅ | ✅ | ✅ | ✅ (chip windows, prior session) |
| Transfers | ✅ | ✅ | ✅ | — (rule-verified, not live-account-verified) |
| Temporal features / leakage guard | ✅ | ✅ | ✅ | ✅ (real GW1 scoring validation, 2 sessions ago) |
| Backtesting | ✅ | ✅ | ✅ | Ready, but 0 real cases exist yet |
| Selling-price rule | ✅ | ✅ | — (not called by anything yet) | Rule-verified via 6 sources, not API-verified |
| Manager account layer | ✅ | ✅ | ✅ (mocked + 1 real-data regression test) | ✅ **CONFIRMED 2026-08-26 — real account, manager 6313636, GW1** |

This is now a genuinely closed loop: the manager layer moved from
"documentation-based, unconfirmed" to "verified against a real,
live-captured response" within the same session, by asking for and
using real evidence instead of proceeding on assumption.
