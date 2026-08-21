# Checkpoint Review — After GW1, Before Phase 6

**As of:** 2026-08-21, post-GW1-deadline, pre-GW1-results.
**Purpose:** honest audit of what's actually connected vs. built-but-inert,
before spending more effort on new phases. Read this before resuming.

---

## 1. What's real and working today

- **The GW1 squad you submitted** came from exactly one path:
  `bootstrap-static.elements[].ep_next` + `status` →
  `baseline/scoring.py` → `baseline/optimizer.py` (MILP, budget/position/
  club constraints) → `baseline/squad_builder.py` (XI, bench order,
  captain/vice with the GK-exclusion fix).
- 105 tests, all passing. ruff clean, mypy `--strict` clean.
- Rules engine (`domain/rules.py`, `scoring_rules.py`, `chips.py`,
  `transfers.py`) is correct and independently verified against the live
  API — but see Section 2.
- Leakage-guarded temporal feature engine (`features/temporal.py`) and a
  backtesting harness (`models/backtest.py`) exist and are correct, but
  have never been run against real data — see Section 3.
- Data ingestion (`data/fpl_client.py`, `data/contracts.py`) pulls and
  validates bootstrap-static, fixtures, and element-summary — but only
  bootstrap-static output is actually consumed downstream. See Section 2.

## 2. Confirmed disconnected (built, tested, unused)

Verified by grep against the actual source tree — not from memory:

| Module | Status | Used by squad_builder / CLI? |
|---|---|---|
| `domain/models.py::Fixture` (fixture difficulty) | ingested + parsed | **No** |
| `domain/models.py::SeasonSummary` (history_past) | ingested + parsed | **No** |
| `domain/chips.py` | correct, tested | **No** |
| `domain/transfers.py` | correct, tested | **No** |
| `features/temporal.py`, `models/backtest.py` | correct, tested | **No real data yet to run on** |

None of this is a defect in the code itself — every one of these modules
does what its tests say it does. The gap is entirely in wiring: each was
built as an isolated, correctly-tested unit and never connected to the
one path that actually produces a recommendation. This is worth naming
plainly as a pattern, not just a list of one-offs — several phases in a
row added a new capability without integrating the previous one.

## 3. Why nothing here changes until GW1 results land

`features/temporal.py`'s leakage guard and `models/backtest.py`'s harness
are both correct, but "correct" was only ever demonstrated against
fixtures I invented. Real per-gameweek data doesn't exist until
`fpl ingest-history` is run after gameweeks are actually played — see
the previous conversation checkpoint. This is a hard blocker, not a
priority call — there is nothing to build here productively right now.

## 4. Technical debt (not urgent, but real)

- **PuLP deprecation warnings** (316 across the suite): `PULP_CBC_CMD` is
  deprecated in favor of `COIN_CMD`, and direct `LpVariable(...)`
  construction is deprecated in favor of `prob.add_variable(...)`. Not
  breaking anything yet, but PuLP 4.0 will remove both. Cheap to fix,
  should happen before it's forced.
- **`cli.py` coverage is 24%**, all in `ingest`, `ingest_history`, and
  `squad_recommend`. This is expected for I/O-glue code (real HTTP calls,
  real file I/O), and unit-testing it meaningfully means mocking
  `FplClient` rather than adding more integration tests — reasonable to
  defer, but it means those three commands have only ever been verified
  by you running them manually, not by the test suite.

## 5. Real bugs this process has already caught (for confidence, not padding)

Evidence the phase-by-phase, test-first discipline is doing its job, not
just adding ceremony:

1. Captain selection defaulted to a goalkeeper on a score tie (caught
   from your actual GW1 output, fixed same day).
2. First chip-window model assumed all four chips shared one uniform
   boundary; real API data showed Wildcard/Free Hit open GW2, not GW1.
3. First EWMA form implementation ranked a declining player above an
   improving one — wrong smoothing factor, caught by a targeted test.
4. An editing mistake deleted `class Fixture(BaseModel):` while adding
   `SeasonSummary` next to it — caught immediately by mypy/ruff, never
   reached a commit.

## 6. Recommended priority order for when we resume

Ranked by (impact on your actual squad quality) ÷ (effort to wire in),
not by roadmap phase number:

1. **Wire fixture difficulty into scoring** — small, contained change to
   `baseline/scoring.py`; data already sits there parsed and unused.
   Matters every gameweek, not just GW1.
2. **Wire `history_past` into the cold-start fallback** — gives new
   signings / promoted-club players a real prior instead of a flat
   position average. Also small and self-contained.
3. **Connect `chips.py` / `transfers.py`** to the CLI so a chip/transfer
   decision is at least representable in a recommendation, even before
   Phase 12's strategic chip *optimizer* exists.
4. **Fix the PuLP deprecation warnings** — cheap, prevents a future
   forced migration under time pressure.
5. **Run `fpl ingest-history --gameweek 2`** once tonight's results are
   final — this is the actual unblock for Phase 6 and for the temporal
   feature engine to do anything on real data for the first time.

Items 1–4 don't depend on GW1 results and can happen anytime. Item 5 is
the one genuinely blocked until results land.
