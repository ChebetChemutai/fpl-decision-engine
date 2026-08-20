# FPL AI Decision Engine

A probabilistic, multi-objective Fantasy Premier League decision-support
platform for the 2026/27 season. Predicts, simulates, and recommends squad,
transfer, captaincy, and chip decisions to maximize the probability of a
user's competitive objectives (season rank, gameweek rank, mini-league rank)
— not simply expected points.

Full concept and architecture: [`docs/architecture.md`](docs/architecture.md).

## Project status

**Phase 1 — Clean Project.** This repository currently contains project
scaffolding only: package structure, configuration, CLI wiring, tests,
linting, and CI. No FPL domain logic, data ingestion, or models exist yet
— those begin at Phase 1.5 (Gameweek 1 baseline) and Phase 2 (domain/rules
engine) respectively. See `docs/architecture.md` Section 16 for the full
phase roadmap.

## Requirements

- Python 3.11+
- Git

## Setup

```bash
git clone <your-repo-url>
cd fpl-decision-engine
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # optional — defaults work out of the box
```

## Usage

```bash
fpl version     # prints the installed package version
fpl info        # prints resolved configuration (env, log level, data dir)
```

## Development

```bash
pytest           # run tests with coverage
ruff check .      # lint
ruff format .     # format
mypy src          # type-check
```

All four must pass before a phase is considered complete (see
`docs/architecture.md` Section 19, Definition of Done).

## Project layout

```
src/fpl_engine/     # application package
tests/              # pytest suite, mirrors src/ structure
data/               # raw/staging/processed data lake (gitignored contents)
docs/               # architecture and phase documentation
.github/workflows/  # CI
```

## Repository conventions

- One meaningful commit per completed unit of work — no empty commits.
- Every phase ends with: tests passing → lint/type-check passing → commit → push.
- See `docs/architecture.md` for the full engineering philosophy.
