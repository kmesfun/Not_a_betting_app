"""Stand-in for the P0.1 data ingestion pipeline.

Real ingestion (live schedules, box scores, transactions, injury reports)
is blocked on the data-licensing question in docs/PRD.md section 1a. This
module generates deterministic mock seed ratings and a mock remaining
schedule so the simulation engine, re-weighting logic, and callable
interface can be built and demoed against realistic-shaped data now,
without depending on that answer. Swap this module out for a real
provider client without touching simulate.py/bracket.py/ratings.py.
"""

from __future__ import annotations

import random


def mock_seed_ratings(teams: list[str], seed: int = 2026) -> dict[str, float]:
    """Deterministic mock Elo seed ratings centered at 1500."""
    rng = random.Random(seed)
    return {team: round(rng.gauss(1500, 90), 1) for team in teams}


def mock_remaining_schedule(
    teams: list[str], games_per_team: int = 20, seed: int = 2026
) -> list[tuple[str, str]]:
    """A mock remaining-games schedule: (home_team, away_team) pairs.

    Not a real NBA schedule (no divisional-weighting/back-to-back rules) —
    just enough structure (each team plays roughly games_per_team games,
    home/away roughly balanced) to exercise the simulator end to end.
    Acceptable as a Phase 1 placeholder; replace with a real schedule feed
    once P0.1 is unblocked.
    """
    rng = random.Random(seed + 1)
    games: list[tuple[str, str]] = []
    games_needed = {team: games_per_team for team in teams}

    while any(count > 0 for count in games_needed.values()):
        available = [team for team, count in games_needed.items() if count > 0]
        if len(available) < 2:
            break
        rng.shuffle(available)
        for i in range(0, len(available) - 1, 2):
            home, away = available[i], available[i + 1]
            if rng.random() < 0.5:
                home, away = away, home
            games.append((home, away))
            games_needed[home] -= 1
            games_needed[away] -= 1

    return games
