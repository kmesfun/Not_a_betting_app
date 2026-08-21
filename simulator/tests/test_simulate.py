from simulator.events import injury, measure_event_impact
from simulator.leagues.nba import LEAGUE, all_teams
from simulator.mock_data import mock_remaining_schedule, mock_seed_ratings
from simulator.ratings import TeamRatings
from simulator.simulate import run_monte_carlo


def _small_league():
    """A 4-team-per-conference cut-down of the NBA config so tests run fast."""
    return {
        "name": "TestLeague",
        "playoff_teams_per_conference": 2,
        "series_best_of": 3,
        "home_advantage_elo": 100,
        "conferences": {
            "East": ["A", "B", "C", "D"],
            "West": ["E", "F", "G", "H"],
        },
    }


def test_probabilities_are_between_0_and_1():
    league = _small_league()
    teams = [t for roster in league["conferences"].values() for t in roster]
    ratings = mock_seed_ratings(teams, seed=1)
    schedule = mock_remaining_schedule(teams, games_per_team=6, seed=1)
    result = run_monte_carlo(league, ratings, schedule, n_sims=300, seed=1)

    for team_prob in result.teams.values():
        assert 0.0 <= team_prob.playoff_probability <= 1.0
        assert 0.0 <= team_prob.conference_probability <= 1.0
        assert 0.0 <= team_prob.championship_probability <= 1.0


def test_probability_ordering_is_consistent():
    """PRD P0.2: championship <= conference title <= playoff appearance."""
    league = _small_league()
    teams = [t for roster in league["conferences"].values() for t in roster]
    ratings = mock_seed_ratings(teams, seed=2)
    schedule = mock_remaining_schedule(teams, games_per_team=6, seed=2)
    result = run_monte_carlo(league, ratings, schedule, n_sims=300, seed=2)

    for team_prob in result.teams.values():
        assert team_prob.championship_probability <= team_prob.conference_probability + 1e-9
        assert team_prob.conference_probability <= team_prob.playoff_probability + 1e-9


def test_championship_probabilities_sum_to_one():
    league = _small_league()
    teams = [t for roster in league["conferences"].values() for t in roster]
    ratings = mock_seed_ratings(teams, seed=3)
    schedule = mock_remaining_schedule(teams, games_per_team=6, seed=3)
    result = run_monte_carlo(league, ratings, schedule, n_sims=300, seed=3)

    total = sum(t.championship_probability for t in result.teams.values())
    assert abs(total - 1.0) < 1e-9


def test_stronger_team_has_higher_championship_probability():
    league = _small_league()
    teams = [t for roster in league["conferences"].values() for t in roster]
    ratings = {t: 1500 for t in teams}
    ratings["A"] = 1900  # dramatically stronger
    schedule = mock_remaining_schedule(teams, games_per_team=6, seed=4)
    result = run_monte_carlo(league, ratings, schedule, n_sims=800, seed=4)

    a_prob = result.teams["A"].championship_probability
    others = [t.championship_probability for name, t in result.teams.items() if name != "A"]
    assert a_prob > max(others)


def test_deterministic_with_fixed_seed():
    league = _small_league()
    teams = [t for roster in league["conferences"].values() for t in roster]
    ratings = mock_seed_ratings(teams, seed=5)
    schedule = mock_remaining_schedule(teams, games_per_team=6, seed=5)

    result_1 = run_monte_carlo(league, ratings, schedule, n_sims=200, seed=99)
    result_2 = run_monte_carlo(league, ratings, schedule, n_sims=200, seed=99)

    for team in ratings:
        assert result_1.teams[team].championship_probability == result_2.teams[team].championship_probability


def test_full_nba_config_runs_end_to_end():
    """Smoke test against the real 30-team NBA config, at a reduced sample
    size so the test suite stays fast (see README for full-scale timing)."""
    teams = all_teams()
    ratings = mock_seed_ratings(teams, seed=2026)
    schedule = mock_remaining_schedule(teams, games_per_team=10, seed=2026)
    result = run_monte_carlo(LEAGUE, ratings, schedule, n_sims=100, seed=2026)

    assert len(result.teams) == 30
    total = sum(t.championship_probability for t in result.teams.values())
    assert abs(total - 1.0) < 1e-9


def test_injury_reduces_championship_probability():
    """PRD P0.3: a significant injury should move title odds down for the
    affected team (direction check, not magnitude calibration -- that
    requires real holdout data per the PRD's validation methodology note)."""
    league = _small_league()
    teams = [t for roster in league["conferences"].values() for t in roster]
    ratings = TeamRatings(base={t: 1500 for t in teams})
    ratings.base["A"] = 1750  # A starts as the clear favorite
    schedule = mock_remaining_schedule(teams, games_per_team=6, seed=6)

    event = injury("A", estimated_win_share_value=150, ramp_games=0)
    report, _ = measure_event_impact(league, ratings, schedule, None, event, n_sims=800, seed=6)

    assert report.delta < 0
