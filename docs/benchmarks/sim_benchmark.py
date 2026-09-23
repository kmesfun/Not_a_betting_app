"""
Monte Carlo season simulator benchmark — NBA & NFL.

Purpose: answer the PRD's open question about compute budget/SLA empirically
rather than by guessing. Fully vectorized across simulations with numpy so the
inner loop is BLAS matmuls, not Python.

Also measures Monte Carlo standard error by sim count, to check whether the
PRD's stated "1,000 simulations" is actually enough precision.
"""

import time
import numpy as np

rng = np.random.default_rng(42)


def elo_win_prob(elo_home, elo_away, hca):
    """Standard Elo expected-score formula with home-court/field advantage."""
    return 1.0 / (1.0 + 10.0 ** ((elo_away - elo_home - hca) / 400.0))


def build_schedule(n_teams, games_per_team, rng):
    """Generate a plausible remaining-schedule as (home_idx, away_idx) arrays."""
    n_games = n_teams * games_per_team // 2
    home = rng.integers(0, n_teams, size=n_games)
    away = rng.integers(0, n_teams, size=n_games)
    # avoid self-matchups
    clash = home == away
    away[clash] = (away[clash] + 1) % n_teams
    return home, away


def simulate_regular_season(n_sims, elo, home, away, hca, existing_wins):
    """
    Simulate every remaining game n_sims times.

    The trick: represent the schedule as incidence matrices so accumulating
    wins per team is a single matmul instead of a scatter-add loop.
    """
    n_teams = len(elo)
    n_games = len(home)

    p_home = elo_win_prob(elo[home], elo[away], hca)          # (G,)
    outcomes = rng.random((n_sims, n_games)) < p_home          # (S, G) home wins

    H = np.zeros((n_games, n_teams), dtype=np.float32)
    A = np.zeros((n_games, n_teams), dtype=np.float32)
    H[np.arange(n_games), home] = 1.0
    A[np.arange(n_games), away] = 1.0

    o = outcomes.astype(np.float32)
    wins = o @ H + (1.0 - o) @ A                               # (S, T)
    return wins + existing_wins


def seed_conference(wins, conf_teams, n_playoff, rng):
    """Rank a conference by wins (random tiebreak) and return seeded team ids."""
    n_sims = wins.shape[0]
    w = wins[:, conf_teams] + rng.random((n_sims, len(conf_teams))) * 0.01
    order = np.argsort(-w, axis=1)[:, :n_playoff]
    return np.asarray(conf_teams)[order]                       # (S, n_playoff)


def play_series(team_a, team_b, elo, hca, best_of):
    """
    Vectorized best-of-N series. team_a has home advantage (higher seed).
    Simulating all N games and taking the majority is equivalent to stopping
    early, and avoids a per-sim while-loop.
    """
    n_sims = len(team_a)
    # home-court split: higher seed hosts the majority of games
    p_a = elo_win_prob(elo[team_a], elo[team_b], hca * 0.5)
    games = rng.random((n_sims, best_of)) < p_a[:, None]
    a_wins = games.sum(axis=1) > (best_of // 2)
    return np.where(a_wins, team_a, team_b)


def run_bracket(seeds, elo, hca, best_of):
    """Single-elimination / series bracket. seeds: (S, n) power-of-two field."""
    field = seeds
    while field.shape[1] > 1:
        n = field.shape[1]
        winners = []
        for i in range(n // 2):
            a = field[:, i]
            b = field[:, n - 1 - i]
            winners.append(play_series(a, b, elo, hca, best_of))
        field = np.stack(winners, axis=1)
    return field[:, 0]


def simulate_nba(n_sims, games_remaining_per_team=25):
    n_teams = 30
    elo = 1500 + rng.normal(0, 110, n_teams)
    hca = 100.0
    home, away = build_schedule(n_teams, games_remaining_per_team, rng)
    existing = rng.integers(20, 40, n_teams).astype(np.float32)

    wins = simulate_regular_season(n_sims, elo, home, away, hca, existing)

    east, west = list(range(15)), list(range(15, 30))
    champs = []
    for conf in (east, west):
        seeds = seed_conference(wins, conf, 8, rng)
        champs.append(run_bracket(seeds, elo, hca, best_of=7))
    finals = play_series(champs[0], champs[1], elo, hca, best_of=7)
    return finals, n_teams


def simulate_nfl(n_sims, games_remaining_per_team=9):
    n_teams = 32
    elo = 1500 + rng.normal(0, 90, n_teams)
    hca = 55.0
    home, away = build_schedule(n_teams, games_remaining_per_team, rng)
    existing = rng.integers(2, 6, n_teams).astype(np.float32)

    wins = simulate_regular_season(n_sims, elo, home, away, hca, existing)

    afc, nfc = list(range(16)), list(range(16, 32))
    champs = []
    for conf in (afc, nfc):
        # 7 playoff teams; #1 seed gets a bye -> treat as 4-team field after wildcard
        seeds = seed_conference(wins, conf, 7, rng)
        # wildcard round: 2v7, 3v6, 4v5
        wc = [play_series(seeds[:, i], seeds[:, 6 - i + 0], elo, hca, 1) for i in (1, 2, 3)]
        divisional_field = np.stack([seeds[:, 0]] + wc, axis=1)
        champs.append(run_bracket(divisional_field, elo, hca, best_of=1))
    sb = play_series(champs[0], champs[1], elo, 0.0, best_of=1)
    return sb, n_teams


def title_probs(winners, n_teams):
    return np.bincount(winners, minlength=n_teams) / len(winners)


def benchmark(label, fn, sim_counts):
    print(f"\n=== {label} ===")
    print(f"{'sims':>8} {'wall time':>12} {'per-sim':>12}  {'top team':>9} {'±SE':>7}  {'longshot ±SE':>13}")
    for n in sim_counts:
        t0 = time.perf_counter()
        winners, n_teams = fn(n)
        dt = time.perf_counter() - t0
        p = title_probs(winners, n_teams)
        top = p.max()
        se_top = np.sqrt(top * (1 - top) / n)
        # a genuine longshot: smallest non-zero probability
        nz = p[p > 0]
        ls = nz.min() if len(nz) else 0.0
        se_ls = np.sqrt(ls * (1 - ls) / n)
        print(f"{n:>8,} {dt:>11.3f}s {dt/n*1e6:>10.1f}µs  {top:>8.1%} {se_top:>6.2%}  "
              f"{ls:>6.2%} ±{se_ls:>5.2%}")
    return


if __name__ == "__main__":
    counts = [1_000, 10_000, 50_000, 200_000]
    benchmark("NBA — 25 games left per team, full playoff bracket", simulate_nba, counts)
    benchmark("NFL — 9 games left per team, full playoff bracket", simulate_nfl, counts)

    # How long does a *full daily refresh* take (both leagues, in season)?
    print("\n=== Full daily refresh (both leagues) ===")
    for n in (1_000, 10_000, 50_000):
        t0 = time.perf_counter()
        simulate_nba(n)
        simulate_nfl(n)
        dt = time.perf_counter() - t0
        print(f"{n:>7,} sims/league: {dt:>7.3f}s")
