"""Elo-style team strength ratings and roster-event (trade/injury) adjustments.

PRD reference: docs/PRD.md P0.3 and section 6. Roster events are phased in
over a configurable ramp rather than applied instantly, per the methodology.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def elo_win_probability(rating_a: float, rating_b: float, home_advantage: float = 0.0) -> float:
    """Probability that team A beats team B, given a home-court edge already
    folded into rating_a (pass home_advantage=0 for a neutral-site game)."""
    diff = (rating_a + home_advantage) - rating_b
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def update_elo(rating_a: float, rating_b: float, score_a: float, k: float = 20.0) -> tuple[float, float]:
    """Post-game Elo update. score_a is 1.0 if A won, 0.0 if A lost."""
    expected_a = elo_win_probability(rating_a, rating_b)
    new_a = rating_a + k * (score_a - expected_a)
    new_b = rating_b + k * ((1.0 - score_a) - (1.0 - expected_a))
    return new_a, new_b


@dataclass
class RosterEvent:
    """A trade or injury applied to one team's rating.

    value_delta is in Elo points: positive for a gain (trade acquisition,
    return from injury), negative for a loss (trade departure, new injury).
    Phased in linearly over ramp_games games rather than applied instantly,
    per PRD section 6 ("new teammates take a few games to integrate").
    """

    team: str
    value_delta: float
    ramp_games: int = 5
    games_elapsed: int = 0
    label: str = ""

    def current_effect(self) -> float:
        if self.ramp_games <= 0:
            return self.value_delta
        fraction = min(1.0, self.games_elapsed / self.ramp_games)
        return self.value_delta * fraction

    def advance(self, games: int = 1) -> None:
        self.games_elapsed = min(self.ramp_games, self.games_elapsed + games)

    def is_fully_ramped(self) -> bool:
        return self.games_elapsed >= self.ramp_games


@dataclass
class TeamRatings:
    """Base Elo ratings plus any in-flight roster events, per team."""

    base: dict[str, float]
    events: dict[str, list[RosterEvent]] = field(default_factory=dict)

    def apply_event(self, event: RosterEvent) -> None:
        self.events.setdefault(event.team, []).append(event)

    def effective_rating(self, team: str) -> float:
        rating = self.base[team]
        for event in self.events.get(team, []):
            rating += event.current_effect()
        return rating

    def advance_all_ramps(self, games: int = 1) -> None:
        for events in self.events.values():
            for event in events:
                event.advance(games)

    def effective_ratings(self) -> dict[str, float]:
        return {team: self.effective_rating(team) for team in self.base}
