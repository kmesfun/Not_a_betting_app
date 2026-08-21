"""Trade/injury event helpers and before/after impact reporting.

PRD reference: docs/PRD.md P0.3 (roster-event re-weighting) and the user
story "I want to see why the odds moved." games_elapsed models how far a
roster event already is into its ramp (e.g. a trade reported 3 days ago
with a 5-game ramp is partway integrated); a real ingestion pipeline would
track and advance this automatically as games are played (P0.1). The MVP
lets the caller pass it explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ratings import RosterEvent, TeamRatings
from .simulate import SimulationBatchResult, run_monte_carlo


def injury(team: str, estimated_win_share_value: float, ramp_games: int = 3, games_elapsed: int = 0, label: str = "") -> RosterEvent:
    """A player ruled out. estimated_win_share_value should be positive
    (the value being lost); it's negated into a rating penalty."""
    return RosterEvent(
        team=team,
        value_delta=-abs(estimated_win_share_value),
        ramp_games=ramp_games,
        games_elapsed=games_elapsed,
        label=label or f"{team} injury",
    )


def trade_leg(team: str, net_value_delta: float, ramp_games: int = 5, games_elapsed: int = 0, label: str = "") -> RosterEvent:
    """One side of a trade. Positive net_value_delta = team gained value,
    negative = team gave up more than it received."""
    return RosterEvent(
        team=team,
        value_delta=net_value_delta,
        ramp_games=ramp_games,
        games_elapsed=games_elapsed,
        label=label or f"{team} trade",
    )


@dataclass
class ImpactReport:
    team: str
    championship_probability_before: float
    championship_probability_after: float

    @property
    def delta(self) -> float:
        return self.championship_probability_after - self.championship_probability_before

    def as_dict(self) -> dict:
        return {
            "team": self.team,
            "championship_probability_before": round(self.championship_probability_before, 4),
            "championship_probability_after": round(self.championship_probability_after, 4),
            "delta": round(self.delta, 4),
        }


def measure_event_impact(
    league_config: dict,
    team_ratings: TeamRatings,
    remaining_schedule: list[tuple[str, str]],
    current_wins: dict[str, int] | None,
    event: RosterEvent,
    n_sims: int = 1000,
    seed: int | None = 2026,
) -> tuple[ImpactReport, SimulationBatchResult]:
    """Run the batch before and after applying event, and report how much
    the affected team's championship odds moved -- the "why did the odds
    move" explainability requirement (P0.6 / P1.4)."""
    before = run_monte_carlo(
        league_config, team_ratings.effective_ratings(), remaining_schedule, current_wins, n_sims=n_sims, seed=seed
    )
    team_ratings.apply_event(event)
    after = run_monte_carlo(
        league_config, team_ratings.effective_ratings(), remaining_schedule, current_wins, n_sims=n_sims, seed=seed
    )
    report = ImpactReport(
        team=event.team,
        championship_probability_before=before.teams[event.team].championship_probability,
        championship_probability_after=after.teams[event.team].championship_probability,
    )
    return report, after
