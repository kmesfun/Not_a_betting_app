import random

from simulator.bracket import (
    order_seeds_for_bracket,
    seed_conference,
    simulate_conference_bracket,
    simulate_series,
    standard_seed_order,
)


def test_standard_seed_order_size_2():
    assert standard_seed_order(2) == [1, 2]


def test_standard_seed_order_size_4():
    assert standard_seed_order(4) == [1, 4, 2, 3]


def test_standard_seed_order_size_8():
    assert standard_seed_order(8) == [1, 8, 4, 5, 2, 7, 3, 6]


def test_standard_seed_order_rejects_non_power_of_two():
    try:
        standard_seed_order(6)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_seed_conference_ranks_by_wins_desc():
    standings = {"A": 50, "B": 40, "C": 60, "D": 10}
    seeds = seed_conference(standings, ["A", "B", "C", "D"], n_teams=3)
    assert seeds == ["C", "A", "B"]


def test_order_seeds_for_bracket_pairs_1_and_8_first():
    seeds = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    ordered = order_seeds_for_bracket(seeds)
    assert (ordered[0], ordered[1]) == ("S1", "S8")


def test_simulate_series_much_stronger_team_almost_always_wins():
    rng = random.Random(42)
    high_win_count = 0
    trials = 200
    for _ in range(trials):
        if simulate_series(2000, 1200, rng, best_of=7, home_advantage=100):
            high_win_count += 1
    assert high_win_count / trials > 0.95


def test_simulate_series_equal_teams_roughly_split_over_many_trials():
    rng = random.Random(7)
    high_wins = sum(1 for _ in range(500) if simulate_series(1500, 1500, rng, best_of=7, home_advantage=0))
    assert 0.35 < high_wins / 500 < 0.65


def test_simulate_conference_bracket_returns_a_seed_from_input():
    rng = random.Random(1)
    seeds = order_seeds_for_bracket([f"T{i}" for i in range(1, 9)])
    ratings = {f"T{i}": 1500 + (9 - i) * 20 for i in range(1, 9)}
    champ = simulate_conference_bracket(seeds, ratings, rng, best_of=7, home_advantage=100)
    assert champ in ratings
