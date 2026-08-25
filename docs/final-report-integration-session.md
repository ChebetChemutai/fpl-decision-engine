# Final Report — Integration and Pre-Phase-6 Hardening

**Session scope:** turn previously-isolated, tested-but-disconnected
capabilities into one coherent, CLI-reachable decision engine, per the
checkpoint review's findings.

---

## 1–3. Files changed / added / removed

**Added:**
- `src/fpl_engine/baseline/fixture_signal.py` (found pre-existing,
  uncommitted, untested at session start — added tests, verified its
  core claim independently, then integrated)
- `src/fpl_engine/baseline/historical_prior.py` (same situation)
- `src/fpl_engine/data/state.py`
- `src/fpl_engine/models/data_pipeline.py`
- `tests/test_fixture_signal.py`, `test_historical_prior.py`,
  `test_enhanced_scoring.py`, `test_cli_integration.py`, `test_state.py`,
  `test_data_pipeline.py`
- `docs/checkpoint-review-gw1.md` (prior session)
- `docs/final-report-integration-session.md` (this file)

**Changed:**
- `src/fpl_engine/baseline/scoring.py` — added `enhanced_score` /
  `score_players_enhanced`, baseline (`score_players`) untouched
- `src/fpl_engine/baseline/squad_builder.py` — added `scored_override`
  parameter
- `src/fpl_engine/baseline/optimizer.py` — PuLP API migration
  (`PULP_CBC_CMD` → `COIN_CMD`, direct `LpVariable` → `problem.add_variable`)
- `src/fpl_engine/cli.py` — added `--mode` to `squad`, added `chip-status`,
  `chip-play`, `transfer-check`, `backtest` commands
- `pyproject.toml` — added `pulp[cbc]` extra

**Removed:** nothing.

## 4. Integration points (grep-verified, not assumed — see commands below)

| Capability | Called from | Verified by |
|---|---|---|
| Fixture difficulty | `cli.py::_build_enhanced_scores` | `team_difficulties_for_gameweek(...)`, `fixture_score_multiplier(...)` actually invoked, not just imported |
| Historical prior | `cli.py::_build_enhanced_scores` | `historical_prior_score(...)` invoked, result fed into `score_players_enhanced` |
| Chips | `cli.py::chip_status`, `chip_play` | `is_gameweek_eligible(...)`, `ChipState.is_available(...)`, `ChipState.play(...)` invoked |
| Transfers | `cli.py::transfer_check` | `calculate_transfer_cost(...)` invoked, result printed |
| Temporal features / backtest | `cli.py::backtest` | `build_backtest_cases`, `build_training_points_by_position`, `run_backtest` invoked in sequence |

Verification command used (not eyeballed): `grep -n "<function>" src/fpl_engine/cli.py`
for each, confirming both the import line and a separate call-site line.

## 5. Fixture scoring design

`team_h_difficulty`/`team_a_difficulty` are each from that team's own
perspective — independently re-confirmed against a live source this
session (not just trusted from an existing code comment). Difficulty
1–5 maps to a multiplier 0.85–1.15 (documented constants, no magic
numbers), centered on 3→1.0. Blank gameweek → multiplier 0.0 (can't
score). Double gameweek → multipliers **sum**, not average (roughly
additive expected points across two matches). Postponed fixtures are
naturally excluded by gameweek-number filtering, no separate flag needed.

## 6. `history_past` fallback design

Three-tier hierarchy: current-season `ep_next` (tier 1) → historical
prior (tier 2, this session's work) → the optimizer's existing
zero-score exclusion (tier 3) → safe neutral. The historical prior
**only** activates when `ep_next == 0` for an otherwise-available
player — not for every low-ep_next player, since a real (if pessimistic)
current projection shouldn't be overridden by a stale one. Requires
≥450 minutes in a season to trust that season's rate at all. Weighted at
0.5× the raw historical points-per-90 rate, reflecting that a prior
season transfers imperfectly (new club, new manager, a year older).

## 7. Temporal leakage guarantees

Re-proven this session through the **full real-ingestion-shaped path**
(`test_data_pipeline.py::test_end_to_end_leakage_guard_holds_through_the_real_ingestion_shaped_path`),
not just re-testing `compute_features` in isolation again. A planted
future-gameweek outlier (9999 points) is confirmed to never influence
an earlier gameweek's prediction, all the way from an unfiltered
multi-player/multi-gameweek history structure through `BacktestCase`
construction to the final MAE. Same guard also applied to baseline
*fitting* (`build_training_points_by_position` excludes the target and
future gameweeks from the training pool), not just per-player features.

## 8. Backtesting integration

`models/data_pipeline.py` bridges real `parse_element_history` output
to `run_backtest`. Against real data today, this correctly and honestly
produces **zero cases** — GW1 has been ingested but not yet played, so
no player has a real result to evaluate against yet. `fpl backtest`
reports this plainly rather than showing a fabricated-looking metric.
Verified both paths: the honest-empty case, and a (synthetic,
explicitly labeled) populated case that runs both baselines and reports
real MAE/RMSE.

## 9. Chip integration

`fpl chip-status --gameweek N` and `fpl chip-play --chip X --gameweek N`.
No eligibility or window logic duplicated in the CLI — both commands
call directly into `domain/chips.py`. Chip usage persisted locally
(`data/state/chips.json`, deliberately separate from `data/raw/`) since
there's no FPL account integration. Strategic chip *optimization*
(when you *should* play a chip) is explicitly out of scope for this
session, per the spec — only legality representation.

## 10. Transfer integration

`fpl transfer-check` validates a candidate transfer (or set of
transfers) against `validate_squad` and computes cost via
`calculate_transfer_cost`. Validation only — no search, no
recommendation of *which* transfer to make. Checks: matching
`--out`/`--in` counts, unknown player IDs, transferring out a player not
in `--current`, resulting-squad legality (budget/position/club), and
warns (doesn't block) on an incoming player who's currently unavailable.

## 11. PuLP migration

Done in a prior part of this session (commit `c0ceed3`), independently
re-verified this session by rerunning the full suite with
`-W error::DeprecationWarning` — passes clean, 0 warnings. Confirmed
`COIN_CMD` availability was checked before migrating (not assumed) per
the commit message; `pulp[cbc]` extra added since bare `COIN_CMD`
doesn't resolve to a working binary in this environment by default.

## 12–13. Tests added / final count

168 tests total (105 at session start, three sessions ago; 133 including
work already in this conversation's history; 168 after this session's
additions). Breakdown of this session's additions: 15 for
fixture_signal/historical_prior (previously zero), 8 for enhanced
scoring, 1 for the `scored_override` integration proof, 3 for chip
state persistence, 22 CLI-level integration tests (chip/transfer/
backtest/squad-mode, all with a mocked `FplClient` — the unit suite
never touches the live API), 7 for the data-pipeline bridge.

## 14. Ruff result

`All checks passed!` — zero errors, zero warnings.

## 15. Mypy result

`Success: no issues found in 27 source files` — strict mode.

## 16. Remaining known limitations

- **No real backtest results exist yet** — by design, not oversight.
  GW1 hasn't been played as of this report. `fpl backtest --gameweek 1`
  will produce a real, non-empty result once `fpl ingest-history` is run
  after tonight's matches finish.
- **Historical prior is single-season** (most recent reliable season
  only) — no multi-season weighted blend. A reasonable scope cut, not
  a bug.
- **Chip state has no undo command** — if a chip is recorded in error,
  the JSON file must be edited or deleted by hand.
- **`transfer-check` takes an explicit `--current` squad every time** —
  there's no persisted "this is my live squad" state the way chips have
  one. A `fpl squad` run doesn't automatically become the tracked
  current squad. Worth a follow-up if this becomes a friction point.
- **CLI coverage is 91%**, not 100% — the uncovered lines are mostly
  `main()`, `if __name__` guards, and a couple of defensive branches
  that would need contrived mocks to hit; not chased further as
  low-value per the "don't add pointless tests just for coverage"
  instruction.
- **No strategic chip or transfer optimizer** — both are, correctly per
  scope, validation/representation only. Recommending *when* to use a
  chip or *which* transfer to make remains future work (Phases 10, 12).

## 17. Exact command to run the recommendation

```bash
fpl ingest --gameweek <N>
fpl ingest-history --gameweek <N>   # optional, enables historical priors
fpl squad --gameweek <N>            # enhanced mode (default)
fpl squad --gameweek <N> --mode baseline   # control-group comparison
```

## 18. Exact command to ingest GW2 history when available

```bash
fpl ingest-history --gameweek 2
fpl backtest --gameweek 1
```

The second command is new this session — once real GW1 results exist,
this is what actually proves (or disproves) whether the enhanced model
beats the baseline on real data, per Section 18 of the integration spec.

---

## IMPLEMENTED vs PROVEN WITH REAL DATA

**IMPLEMENTED and unit/integration-tested:** everything in this report.

**NOT YET PROVEN WITH REAL DATA:** whether the enhanced model (fixture
difficulty + historical priors) actually produces better recommendations
than the baseline. That claim cannot be made yet — it requires
`fpl backtest` to run against real post-match results, which don't exist
until gameweeks are actually played. This report does not claim
empirical improvement; it claims the plumbing is real, tested, and ready
to produce that answer honestly once the data exists.
