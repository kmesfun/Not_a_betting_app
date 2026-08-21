from simulator.ratings import RosterEvent, TeamRatings, elo_win_probability, update_elo


def test_elo_win_probability_symmetry():
    p_a = elo_win_probability(1600, 1500)
    p_b = elo_win_probability(1500, 1600)
    assert abs((p_a + p_b) - 1.0) < 1e-9
    assert p_a > 0.5


def test_elo_win_probability_equal_ratings_is_half():
    assert abs(elo_win_probability(1500, 1500) - 0.5) < 1e-9


def test_home_advantage_increases_win_probability():
    neutral = elo_win_probability(1500, 1500, home_advantage=0)
    home = elo_win_probability(1500, 1500, home_advantage=100)
    assert home > neutral


def test_update_elo_winner_gains_loser_loses():
    new_a, new_b = update_elo(1500, 1500, score_a=1.0, k=20)
    assert new_a > 1500
    assert new_b < 1500
    assert abs((new_a - 1500) - (1500 - new_b)) < 1e-9


def test_roster_event_ramp_is_partial_then_full():
    event = RosterEvent(team="BOS", value_delta=-40, ramp_games=4, games_elapsed=0)
    assert event.current_effect() == 0
    event.advance(2)
    assert event.current_effect() == -20
    event.advance(2)
    assert event.current_effect() == -40
    assert event.is_fully_ramped()


def test_roster_event_ramp_does_not_overshoot():
    event = RosterEvent(team="BOS", value_delta=-40, ramp_games=4)
    event.advance(100)
    assert event.current_effect() == -40


def test_zero_ramp_is_immediate():
    event = RosterEvent(team="BOS", value_delta=-40, ramp_games=0)
    assert event.current_effect() == -40


def test_team_ratings_effective_rating_applies_events():
    ratings = TeamRatings(base={"BOS": 1600, "LAL": 1550})
    ratings.apply_event(RosterEvent(team="BOS", value_delta=-30, ramp_games=0))
    assert ratings.effective_rating("BOS") == 1570
    assert ratings.effective_rating("LAL") == 1550


def test_team_ratings_stacks_multiple_events():
    ratings = TeamRatings(base={"BOS": 1600})
    ratings.apply_event(RosterEvent(team="BOS", value_delta=-30, ramp_games=0))
    ratings.apply_event(RosterEvent(team="BOS", value_delta=10, ramp_games=0))
    assert ratings.effective_rating("BOS") == 1580
