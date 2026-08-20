# FPL AI Decision Engine — Phase 0: Concept & Architecture Specification
**Season:** 2026/27 | **Status:** Pre-implementation review | **Author:** Lead Engineer (Claude), for review by project owner

---

## 1. Conceptual Specification

### 1.1 What this system is
A decision-support engine that, given the current state of the FPL world (prices, fixtures, form, ownership, the user's squad, chip status, mini-league standings) and a set of available decisions (transfers, captain, chips), outputs the action that maximizes the *probability* of the user's stated competitive objectives — not the action that maximizes *expected points*. Expected points is one input signal among several (variance, ceiling/floor, ownership, rank pressure, remaining fixtures).

### 1.2 What this system is not
- Not a raw point predictor with a leaderboard bolted on.
- Not a "highest xPts XI" generator — that's a special case (risk-neutral, no rank pressure) the engine can produce, not its purpose.
- Not a rules-agnostic model — every recommendation must be legal under the *current* season's FPL rules, enforced by a dedicated, testable rules layer.

### 1.3 Core objective (informal)
```
maximize  P(Elite Outcome | current_state, decision)
where Elite Outcome ∈ {Season Top 10/Top 3, GW Top 10, Mini-League Top 3/#1}
```
This is never computed as a closed-form probability. It is *estimated* — from historical distributions, simulated outcomes, and calibrated model uncertainty — and the estimate's confidence is always surfaced alongside the recommendation. The system should be explicit with itself and the user about the difference between "we simulated this" and "we know this."

### 1.4 Strategic modes
Because the four objectives (season rank, GW rank, mini-league rank, and their sub-targets) can conflict, the Decision layer operates in one of four modes, selectable by the user but defaulting to **BALANCED**:

| Mode | Optimizes for | Risk posture |
|---|---|---|
| BALANCED | Blend of all four, weighted by current gap-to-target | Moderate |
| SEASON ATTACK | Overall rank (Top 10/Top 3) | Low-variance, template-adjacent unless behind |
| GAMEWEEK ATTACK | Single-GW rank | High-variance, differential-seeking |
| MINI-LEAGUE ATTACK | Rank vs. named rivals | Directly conditioned on rival squads/captains |

Mode selection changes *which* simulated outcome distribution the optimizer scores against — it does not change the underlying predictions.

---

## 2. System Architecture (Three Layers, Enforced)

```
PREDICTION  →  SIMULATION  →  DECISION
"what's      "what could      "what should
 likely?"     happen?"         we do?"
```

**Why enforced separation matters here specifically:** the biggest failure mode in FPL modeling projects is silently mixing "expected value" logic into what should be a probability/strategy layer (e.g., a squad optimizer that secretly just sorts by xPts). Keeping these as distinct modules with distinct, testable contracts is what makes the "Player A vs Player B under rank pressure" example in your brief actually work — Layer 3 has to be able to re-score the *same* Layer 2 simulation output under different mode/state inputs without touching Layer 1 or 2.

Full pipeline (data → Flutter) as you specified — no changes to your diagram; noting it below in words rather than re-drawing it since the ASCII version you provided is already correct:

Data Sources → Ingestion → Validation → Temporal Feature Engine V4 (historical mode / live mode, same contract) → Feature Validation & Leakage Detection → Prediction Ensemble → Calibration → Monte Carlo Engine → FPL Decision Engine (squad/XI/bench/captain/transfers/chips) → Opponent Intelligence → Global Competitive Engine → Decision + Explanation → Backend API → Flutter App.

---

## 3. Domain Model

Core entities (conceptual, not code):

- **Player** — identity, position, club, price, status (available/injured/suspended/doubtful), ownership%, transfers in/out.
- **Team** (club) — attacking/defensive strength ratings, fixture list.
- **Fixture** — home/away pair, kickoff, gameweek, difficulty.
- **Gameweek** — deadline, fixtures, blank/double flags, chip-eligibility state.
- **Squad** (user's) — 15 players, budget remaining, free transfers, chip inventory, chip-used history.
- **SquadSnapshot** — a squad as of a specific deadline (immutable, versioned — needed for backtesting and for "what did we recommend vs. what happened").
- **Rival** — a mini-league opponent's squad, captured the same way as SquadSnapshot.
- **Prediction** — versioned, tied to a model version, feature version, and target gameweek.
- **SimulationResult** — versioned, tied to a prediction set and a random seed.
- **Decision/Recommendation** — the final output object: action, rationale, confidence, alternatives, risk.

Rule of thumb for the domain layer: everything that will later need to be *compared over time* (predictions, squads, decisions) must be immutable and versioned. Nothing gets overwritten in place — this is what makes the continuous learning loop (Section 23 of your brief) possible at all.

---

## 4. Data Architecture

```
data/
  raw/snapshots/{source}/{season}/{gw}/{timestamp}.json   # never overwritten
  staging/                                                 # validated, normalized, still source-shaped
  processed/                                               # feature-ready, contract-shaped
```

- Each raw snapshot records source, timestamp, season, gameweek, and schema version — enabling replay of "what did we know as of GW N deadline."
- Provider interfaces (`FplDataProvider` protocol) decouple ingestion from source specifics, so a source change or API break doesn't ripple into the feature engine.
- Data contracts (Pydantic schemas) sit at the staging→processed boundary and are the enforcement point for "no future information" — see Section 6.

---

## 5. ML Architecture

- **Baselines first**: position-average, recent-form-weighted average, and simple linear models are the floor every later model must beat on held-out gameweeks before it's allowed into the ensemble.
- **Component models** (minutes, goals, assists, clean sheets, defensive contributions, bonus, cards) predicted separately, then FPL points *derived* from the current season's scoring rules — not predicted directly. This is what makes explanations possible ("captain pick driven by high start-probability + strong underlying attacking numbers" instead of an opaque single score) and what makes the simulation layer meaningful (you can't Monte-Carlo a single point estimate usefully; you can Monte-Carlo minutes × goal-involvement).
- **Minutes model is first-class**, not a feature: P(start), P(appearance), P(60+), rotation risk. Every downstream expected-points calculation is conditioned on it.
- **Model selection** by measured temporal backtest performance (see Section 8), not by complexity. Gradient-boosted trees (LightGBM/XGBoost/CatBoost) are the expected ceiling for a project this size given feature volume; neural models are out of scope unless a specific gap is demonstrated.
- **Calibration** as its own step: Brier score, log loss, reliability curves, tracked per model version. Calibrated probabilities are what feed Monte Carlo — uncalibrated point predictions would make the simulation's probability outputs (P(Top 10) etc.) meaningless.

---

## 6. Temporal Feature Engine (V4) Architecture

The single most important correctness property in the whole system: **for a prediction targeting Gameweek N, no feature may be derived from information not available before GW N's deadline.**

- Historical (training) mode and live (inference) mode must produce features through the *same code path and the same contract* — a single `FeatureContractV4` schema — so training/serving skew is structurally prevented rather than tested for after the fact.
- Cold start handled explicitly (Section 7 below), never as silent zero-fill.
- Automated leakage tests: for every feature, assert its value at GW N is computable using only data timestamped strictly before GW N's deadline. This should run in CI on every change to the feature engine, not just once.

Feature families as you specified (Player / Team / Fixture / Market / Temporal) — no changes needed there.

---

## 7. Cold Start Strategy

Four distinct states, never collapsed into one:
- **True zero** (player played and recorded zero of a stat) — a real, informative value.
- **Missing** (data not yet available / not yet collected).
- **Insufficient history** (player exists but hasn't accumulated enough gameweeks for a stable rolling stat).
- **Not applicable** (e.g., goalkeeper xA).

New players fall back to population → position → team priors, in that order of specificity as data becomes available, with the fallback tier used explicitly recorded on the feature row (so a "confident" vs. "cold-start" prediction can be distinguished downstream and surfaced in the UI's confidence indicator).

---

## 8. Simulation & Optimization Architecture

- **Monte Carlo engine**: samples from calibrated component-model distributions (not point estimates) to produce per-player, per-squad, per-rival outcome distributions. Deterministic seeding required for test reproducibility; production runs use fresh entropy scaled to the mode (thousands for a quick captain check, tens of thousands for a season-outlook query).
- **Squad/XI/transfer/captaincy/chip optimizers** are constrained-optimization problems (OR-Tools/PuLP) that consume simulation *distributions*, not raw predictions, so that Section 2's mode-dependent scoring (variance-seeking vs. variance-averse) is a parameter to the optimizer's objective function, not a different codepath.
- **Backtesting** is temporal by construction: a model/optimizer combination is only validated by replaying past gameweeks using only data available at the time, never by k-fold shuffling across gameweeks (which would leak future information across the split).

---

## 9. Opponent Intelligence Architecture

Ingests rival squads (available via FPL's public league/entry endpoints) as the same `SquadSnapshot` type used for the user's own squad — this reuse is deliberate, it means the Global Competitive Engine can score "your squad vs. a simulated GW outcome" and "rival squad vs. the same simulated GW outcome" through identical code. Outputs Threat Score, Differential Opportunity, and Rank Pressure per rival, always as probability-weighted estimates, never as claimed certainty about a rival's future transfer or chip use.

---

## 10. Global Competitive Engine Architecture

Consumes: user squad simulation outcomes, rival simulation outcomes (where available), and a population model (Section 22 of your brief) for gameweeks/leagues where no direct rival data exists (overall/GW-wide rank). Produces the four headline probabilities (Season Top 3/Top 10, GW Top 10, Mini-League Top 3) plus the mode-weighted composite the Decision layer optimizes against.

---

## 11. Backend/API Architecture

FastAPI, versioned (`/api/v1/...`) exactly as you listed. Layering inside the backend:
```
Router (FastAPI) → Application Service → Decision Engine → ML/Simulation/Optimization → Data Layer
```
Flutter never sees model internals — only recommendation objects (action, rationale, confidence, alternatives). This boundary is what lets the ML side be rebuilt or swapped (e.g., baseline → gradient-boosted) without touching the app.

---

## 12. Flutter Architecture

Presentation-only, as specified: Home, My Squad, AI Recommendation, Player Analysis, Transfers, Chips, Mini-League, Simulation. State management choice deferred to Phase 16 (deliberately — premature choice here is a common over-engineering trap); the API contract from Section 11 should be stable enough that this decision doesn't block earlier phases.

---

## 13. Database Architecture

Separate schemas/tables for: raw FPL reference data, features (versioned), predictions (versioned, immutable), model versions, simulation results, user/team data, league/rival data, decisions/recommendations (versioned). No table mixes raw ingested data with derived application state — this mirrors the `data/raw` vs `data/processed` filesystem split at the database layer.

---

## 14. Testing Strategy

- **Unit**: rules engine (scoring, constraints, chip legality) — highest priority, since an illegal recommendation is a worse failure than a suboptimal one.
- **Leakage tests**: automated, run on every feature-engine change (Section 6).
- **Backtests**: temporal, gameweek-by-gameweek replay (Section 8) — this is the primary evidence for "is this model actually good," not offline accuracy metrics alone.
- **Contract tests**: Pydantic schema validation at every data-layer boundary (raw→staging→processed→feature).
- **Integration**: end-to-end "given a GW deadline snapshot, does the pipeline produce a legal, explainable recommendation" test, run per phase from Phase 9 onward.

Failing tests block phase completion (Section 30 of your brief) — no exceptions without written justification in the commit.

---

## 15. Git/GitHub Workflow

- One meaningful commit per completed unit of work; message states what changed and why (not "wip" or "fix").
- Every phase ends: tests pass → `git status` reviewed → commit → push.
- No commits solely to preserve a streak — a documented "no meaningful progress today" is fine; an empty commit is not, per your own principle in Section 32.

---

## 16. Development Roadmap

Your 20-phase roadmap (Sections 31.0–31.20 of your brief) is sound as written and I'm not proposing changes to phase ordering. One adjustment worth flagging for your review: **Track A (GW1 baseline squad) should run as an explicit Phase 1.5**, sitting between Phase 1 (clean project) and Phase 2 (full domain/rules build), rather than floating outside the phase numbering as "Track A / Track B." Reasoning: Phase 1.5's rules subset (scoring, squad constraints, budget) is a strict subset of what full Phase 2 needs, so building it as a small, real, tested slice first gives you (a) a working GW1 recommendation fast, and (b) a partially-built, already-tested rules engine to extend in Phase 2, rather than throwaway scaffolding.

---

## 17. Immediate Gameweek 1 Plan (Track A / Phase 1.5)

Minimum vertical slice, using real current-season data only:
1. Rules subset: squad constraints (2 GK/5 DEF/5 MID/3 FWD, £100m budget, max 3 per club), current scoring rules, valid formations.
2. Data: single ingestion pull of current player prices, current fixtures (GW1), and prior-season final-form stats where a player has history.
3. Model: simple baseline expected-points score (form-weighted, fixture-adjusted, minutes-probability-gated) — explicitly labeled as a baseline in all outputs, not the full ensemble.
4. Optimizer: constrained squad selection (highest-baseline-score legal squad within budget/constraints) + naive captain (highest expected points among high-start-probability players).
5. Output: 15-man squad, XI, bench order, captain, vice-captain, one-paragraph rationale per key decision.

This does not use simulation, calibration, or the global competitive engine — those come online in later phases and the GW1 baseline is expected to be superseded quickly.

---

## 18. Risks & Technical Unknowns

| Risk | Notes |
|---|---|
| FPL API stability/rate limits | Public API is unofficial; provider-interface pattern (Section 4) mitigates but doesn't eliminate breakage risk |
| Rival data availability | Mini-league opponent squads are only visible for leagues the user is in and only current/past GWs — no future rival intent, ever (probabilistic modeling only) |
| Cold-start accuracy for promoted teams/new signings | No FPL history exists yet; population priors will be materially less accurate than for established players/teams, and this should be surfaced as lower confidence, not hidden |
| Defensive contribution scoring stability | New-ish rule category league-wide; historical training data for it is thin — flag predictions in this area as lower-confidence until more seasons accumulate |
| Blank/double gameweek modeling | Low-frequency, high-impact events — backtesting coverage will be sparse; treat these as a later-phase refinement, not a GW1 requirement |
| Simulation compute cost at 50k–100k runs | Needs a performance check before Phase 11 is considered done — may need vectorized (NumPy) simulation rather than naive looping |
| "Elite outcome" probability estimates | These are estimates with real uncertainty, especially early season (small sample). All UI surfacing of P(Top 10) etc. must carry a confidence/uncertainty indicator, not a bare number |

---

## 19. Definition of Done (per phase)

A phase is done when, and only when: implementation is complete for that phase's stated scope (no partial/placeholder logic), tests exist and pass, the phase's own leakage/contract tests pass where applicable, documentation (what/why, not just docstrings) is written, a git commit with a real message is pushed, and the repository is left in a runnable state — the next phase should be able to start from a clean checkout with no manual fixup steps.

---

## Review Checkpoint

This is the full Phase 0 deliverable per your FIRST COMMAND. I have **not** started Phase 1 or written any implementation code. The one substantive proposal above (Section 16 — inserting Phase 1.5 for the GW1 baseline) is the one thing I'd like your explicit sign-off on before we start, since it slightly reorders your roadmap; everything else follows your brief as written.

Say **"proceed to Phase 1"** (or push back on Section 16 first) when ready.
