"""Monte Carlo season simulation engine.

PRD reference: docs/PRD.md P0.2 and section 6. This runs N independent
full-season simulations (default N = 1000) -- in each one, every remaining
game is simulated exactly once and results roll forward through the
playoff bracket to a single champion -- then aggregates across the N runs.
This is deliberately NOT "1000 independent replays of each individual
game", which was the ambiguous v1 reading called out in the PRD critique.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .bracket import order_seeds_for_bracket, seed_conference, simulate_conference_bracket, simulate_series
from .ratings import elo_win_probability

# Below this sample-size-relative-to-estimate ratio, flag the estimate as
# low-confidence rather than presenting day-to-day noise as a real movement.
# See docs/PRD.md P0.2 acceptance criteria.
NOISE_FLAG_SE_OVER_P_THRESHOLD = 0.20


@dataclass
class TeamOutcomeCounts:
    playoff_appearances: int = 0
    conference_titles: int = 0
    championships: int = 0


@dataclass
class TeamProbability:
    team: str
    playoff_probability: float
    conference_probability: float
    championship_probability: float
    championship_standard_error: float
    low_confidence: bool

    def as_dict(self) -> dict:
        return {
            "team": self.team,
            "playoff_probability": round(self.playoff_probability, 4),
            "conference_probability": round(self.conference_probability, 4),
            "championship_probability": round(self.championship_probability, 4),
            "championship_standard_error": round(self.championship_standard_error, 4),
            "low_confidence": self.low_confidence,
        }


@dataclass
class SimulationBatchResult:
    n_sims: int
    teams: dict[str, TeamProbability] = field(default_factory=dict)

    def sorted_by_championship(self) -> list[TeamProbability]:
        return sorted(self.teams.values(), key=lambda t: -t.championship_probability)


def _simulate_regular_season(
    schedule: list[tuple[str, str]],
    effective_ratings: dict[str, float],
    current_wins: dict[str, int],
    rng: random.Random,
    home_advantage: float,
) -> dict[str, int]:
    wins = dict(current_wins)
    for home, away in schedule:
        p_home = elo_win_probability(effective_ratings[home], effective_ratings[away], home_advantage=home_advantage)
        if rng.random() < p_home:
            wins[home] = wins.get(home, 0) + 1
        else:
            wins[away] = wins.get(away, 0) + 1
    return wins


def _simulate_playoffs(
    conferences: dict[str, list[str]],
    final_wins: dict[str, int],
    effective_ratings: dict[str, float],
    rng: random.Random,
    playoff_teams_per_conference: int,
    series_best_of: int,
    home_advantage: float,
) -> tuple[str, dict[str, str]]:
    conference_champions: dict[str, str] = {}
    for conf, roster in conferences.items():
        seeds = seed_conference(final_wins, roster, playoff_teams_per_conference)
        ordered = order_seeds_for_bracket(seeds)
        champ = simulate_conference_bracket(
            ordered, effective_ratings, rng, best_of=series_best_of, home_advantage=home_advantage
        )
        conference_champions[conf] = champ

    conf_names = list(conference_champions.keys())
    a, b = conference_champions[conf_names[0]], conference_champions[conf_names[1]]
    a_is_champion = simulate_series(
        effective_ratings[a], effective_ratings[b], rng, best_of=series_best_of, home_advantage=home_advantage
    )
    champion = a if a_is_champion else b
    return champion, conference_champions


def run_monte_carlo(
    league_config: dict,
    effective_ratings: dict[str, float],
    remaining_schedule: list[tuple[str, str]],
    current_wins: dict[str, int] | None = None,
    n_sims: int = 1000,
    seed: int | None = None,
) -> SimulationBatchResult:
    """Run n_sims full-season simulations and aggregate outcome
    probabilities per team, per docs/PRD.md P0.2."""
    conferences: dict[str, list[str]] = league_config["conferences"]
    all_teams = [team for roster in conferences.values() for team in roster]
    current_wins = current_wins or {team: 0 for team in all_teams}
    playoff_teams_per_conference = league_config["playoff_teams_per_conference"]
    series_best_of = league_config["series_best_of"]
    home_advantage = league_config["home_advantage_elo"]

    rng = random.Random(seed)
    counts = {team: TeamOutcomeCounts() for team in all_teams}

    for _ in range(n_sims):
        final_wins = _simulate_regular_season(remaining_schedule, effective_ratings, current_wins, rng, home_advantage)
        champion, conference_champions = _simulate_playoffs(
            conferences, final_wins, effective_ratings, rng, playoff_teams_per_conference, series_best_of, home_advantage
        )

        for conf, roster in conferences.items():
            for team in seed_conference(final_wins, roster, playoff_teams_per_conference):
                counts[team].playoff_appearances += 1

        for team in conference_champions.values():
            counts[team].conference_titles += 1

        counts[champion].championships += 1

    result = SimulationBatchResult(n_sims=n_sims)
    for team, c in counts.items():
        p_champ = c.championships / n_sims
        se = math.sqrt(p_champ * (1 - p_champ) / n_sims)
        low_confidence = p_champ > 0 and (se / p_champ) > NOISE_FLAG_SE_OVER_P_THRESHOLD
        result.teams[team] = TeamProbability(
            team=team,
            playoff_probability=c.playoff_appearances / n_sims,
            conference_probability=c.conference_titles / n_sims,
            championship_probability=p_champ,
            championship_standard_error=se,
            low_confidence=low_confidence,
        )
    return result
