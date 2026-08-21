"""Playoff seeding and single-elimination bracket simulation.

Simplified vs. real NBA rules (no play-in tournament, no tiebreaker
procedures) — acceptable for a Phase 1 MVP per docs/PRD.md section 6,
which flags full bracket fidelity as a real engineering subproblem to
harden later, not a Phase 1 requirement.
"""

from __future__ import annotations

import random

from .ratings import elo_win_probability


def standard_seed_order(bracket_size: int) -> list[int]:
    """Standard tournament seeding order (1-indexed) for a power-of-two
    bracket, e.g. size 8 -> [1, 8, 4, 5, 2, 7, 3, 6], so that consecutive
    pairs in the list are the correct first-round matchups and winners of
    consecutive pairs feed each subsequent round correctly."""
    if bracket_size & (bracket_size - 1) != 0:
        raise ValueError("bracket_size must be a power of two")
    order = [1]
    size = 1
    while size < bracket_size:
        size *= 2
        order = [x for s in order for x in (s, size + 1 - s)]
    return order


def seed_conference(standings: dict[str, int], teams: list[str], n_teams: int) -> list[str]:
    """Top n_teams by wins (ties broken by rating, then name, for
    determinism), highest seed first."""
    ranked = sorted(teams, key=lambda t: (-standings[t], t))
    return ranked[:n_teams]


def simulate_series(
    rating_high_seed: float,
    rating_low_seed: float,
    rng: random.Random,
    best_of: int = 7,
    home_advantage: float = 100.0,
) -> bool:
    """Simulate a best-of-N series between the higher and lower seed.
    Returns True if the higher seed wins. Home court follows a 2-2-1-1-1
    pattern favoring the higher seed."""
    wins_needed = best_of // 2 + 1
    high_wins = 0
    low_wins = 0
    game = 0
    # Home-court pattern for a 7-game series; truncated for shorter series.
    home_pattern = [True, True, False, False, True, False, True]
    while high_wins < wins_needed and low_wins < wins_needed:
        high_at_home = home_pattern[game % len(home_pattern)]
        home_adv = home_advantage if high_at_home else -home_advantage
        p_high = elo_win_probability(rating_high_seed, rating_low_seed, home_advantage=home_adv)
        if rng.random() < p_high:
            high_wins += 1
        else:
            low_wins += 1
        game += 1
    return high_wins > low_wins


def simulate_conference_bracket(
    seeds: list[str],
    ratings: dict[str, float],
    rng: random.Random,
    best_of: int,
    home_advantage: float,
) -> str:
    """seeds is ordered by standard_seed_order (already reordered so
    consecutive pairs are correct matchups). Returns the conference
    champion."""
    round_teams = list(seeds)
    while len(round_teams) > 1:
        next_round: list[str] = []
        for i in range(0, len(round_teams), 2):
            high, low = round_teams[i], round_teams[i + 1]
            high_wins = simulate_series(
                ratings[high], ratings[low], rng, best_of=best_of, home_advantage=home_advantage
            )
            next_round.append(high if high_wins else low)
        round_teams = next_round
    return round_teams[0]


def order_seeds_for_bracket(seeded_teams: list[str]) -> list[str]:
    """seeded_teams is [seed_1, seed_2, ..., seed_n] best-to-worst.
    Reorders into standard bracket play order."""
    order = standard_seed_order(len(seeded_teams))
    return [seeded_teams[s - 1] for s in order]
