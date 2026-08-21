# Live Season Simulator — Phase 1 MVP

Implements the Phase 1 slice of [docs/PRD.md](../docs/PRD.md): a Monte Carlo
NBA season simulator with championship/conference/playoff-appearance
probabilities, trade/injury re-weighting with an explainability report, and
a callable interface (CLI + optional HTTP API). No awards or positional
rankings yet — those are Phase 2.

**This runs entirely on mock data.** Real ingestion (P0.1) is blocked on
the data-licensing question in PRD section 1a — whether a real-time sports
data provider's license permits a public probability/ranking product. Until
that's resolved, [`mock_data.py`](src/simulator/mock_data.py) generates
deterministic mock team ratings and a mock remaining schedule so the
simulation engine, re-weighting logic, and callable interface can all be
built and demoed now. Swap `mock_data.py` for a real provider client
without touching `simulate.py`, `bracket.py`, or `ratings.py`.

## What this proves out

- **P0.2 Monte Carlo engine**: `simulate.py` runs N full-season simulations
  (default 1,000) — each one plays every remaining game once and rolls
  forward through a seeded single-elimination playoff bracket to a champion
  — then aggregates into per-team probabilities with standard error. This
  is the season-level interpretation the PRD critique flagged as ambiguous
  in v1 ("1,000 sims per game" vs. "1,000 full-season sims").
- **P0.3 re-weighting**: `ratings.py`'s `RosterEvent` applies a trade/injury
  as an Elo-point delta, phased in linearly over a configurable ramp.
  `events.py` runs the batch before/after an event and reports the
  direction and magnitude of the odds movement (the "why did the odds
  move" user story / P1.4).
- **P0.2 noise floor**: teams whose championship-probability standard error
  is large relative to the estimate get flagged `low_confidence: true`
  rather than presenting sampling noise as a real signal.
- **P0.6 callable interface**: `cli.py` (`python -m simulator.cli update`)
  and `api.py` (FastAPI) both serve the same underlying report, each
  stating an `as_of` timestamp, and both support scoping to a single team.
- **Dashboard** (`static/index.html`, served at `/`): a ranked championship-odds
  table for all 30 teams with proportional bars and low-confidence flags, plus
  two "what if?" panels that call `/v1/explain-injury` and `/v1/explain-trade`
  live and show the before/after odds movement — the P0.3/P1.4 explainability
  story made interactive rather than CLI-only.

## Known Phase 1 simplifications (see inline comments for each)

- Mock data, not a real provider feed (blocked on PRD §1a).
- Playoff bracket has no play-in tournament or NBA tiebreaker rules —
  straight top-8-per-conference seeding.
- No persistence layer: every CLI/API call regenerates ratings and schedule
  fresh from `--seed`; there's no "current standings so far this season"
  carried between calls.
- The API runs the simulation batch synchronously per request rather than
  serving a precomputed scheduled batch (see docstring in `api.py`) — fine
  at n_sims=1000 for a demo, not yet the real P0.6 NFR.

## Setup

```bash
cd simulator
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install -r requirements.txt
```

## Run it

```bash
# Today's update, full league, 1000 sims (P0.2 default)
.venv/bin/python -m simulator.cli update

# Scoped to one team (P0.6 acceptance criterion)
.venv/bin/python -m simulator.cli update --team BOS

# "Why did the odds move" for an injury (P0.3 / P1.4)
.venv/bin/python -m simulator.cli explain-injury --team OKC --value 200 --ramp 0

# Same, for a trade (both sides)
.venv/bin/python -m simulator.cli explain-trade --team-in BOS --team-out MIA --value 150 --ramp 0

# HTTP form of the callable interface, plus the dashboard at "/"
.venv/bin/uvicorn simulator.api:app --reload
open http://127.0.0.1:8000/          # dashboard
curl "http://127.0.0.1:8000/v1/update?team=BOS"
```

## Test

```bash
.venv/bin/python -m pytest -q
```

Covers: Elo math, ramp behavior, standard playoff seeding order (verified
against known bracket shapes for sizes 2/4/8), the P0.2 probability
consistency invariant (championship ≤ conference ≤ playoff appearance),
determinism under a fixed seed, and that an injury to a heavy favorite
moves their title odds down.
