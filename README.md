# Live Season Simulator

A daily-refreshed, explainable Monte Carlo season simulator for NBA and NFL —
championship odds, award races, and positional player rankings, callable
on demand instead of browsed on a dashboard. See [`docs/PRD.md`](docs/PRD.md)
for the full product spec, including the sports-data-licensing risk (§1a)
that currently blocks real data ingestion.

## What's here

- [`docs/PRD.md`](docs/PRD.md) — the product spec (v2, revised after review).
- [`simulator/`](simulator/) — the Phase 1 MVP: an NBA Monte Carlo
  championship simulator with trade/injury re-weighting, a callable
  CLI/API interface, and a small dashboard. Runs entirely on mock data
  pending the data-licensing decision. See
  [`simulator/README.md`](simulator/README.md) for setup and usage.

## Quick start

```bash
cd simulator
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install -r requirements.txt

.venv/bin/python -m simulator.cli update          # today's odds, CLI
.venv/bin/uvicorn simulator.api:app --reload       # API + dashboard at http://127.0.0.1:8000/
.venv/bin/python -m pytest -q                      # 41 tests
```

## Status

Phase 1 (core simulator + championship odds + callable interface) is
implemented against mock data. Phases 2–4 (awards, positional rankings,
a second league, notifications/personalization) are scoped in the PRD but
not yet built — see §9 for the phasing and the Phase 0 gate on data
licensing.
