"""Callable interface, CLI form: `python -m simulator.cli ...`.

PRD reference: docs/PRD.md P0.6 and the user story "I want to 'call' the
app daily... rather than remembering to check a website." This is the
Phase 1 stand-in for that callable surface (chat/notification/REST are
still open per PRD section 8); a FastAPI wrapper (api.py) exposes the same
logic over HTTP.

State note: this MVP has no persistence layer (that's P0.1's job, blocked
per PRD section 1a). Each CLI invocation regenerates mock seed ratings and
a mock remaining schedule deterministically from --seed, and treats it as
"the season from here" with current_wins at 0 for every team. Wire a real
current-standings/ratings store in behind mock_data.py once ingestion
lands.
"""

from __future__ import annotations

import argparse
import json
import sys

from .events import injury, measure_event_impact, trade_leg
from .leagues import LEAGUES
from .mock_data import mock_remaining_schedule, mock_seed_ratings
from .ratings import TeamRatings
from .report import build_update
from .simulate import run_monte_carlo


def _load_league(league_key: str) -> dict:
    try:
        return LEAGUES[league_key]
    except KeyError as exc:
        available = ", ".join(sorted(LEAGUES))
        raise SystemExit(f"Unknown league '{league_key}'. Available: {available}") from exc


def _team_ratings(league_config: dict, seed: int) -> TeamRatings:
    teams = [t for roster in league_config["conferences"].values() for t in roster]
    return TeamRatings(base=mock_seed_ratings(teams, seed=seed))


def _normalize_team(team_ratings: TeamRatings, team: str | None, league_key: str) -> str | None:
    """Upper-cases and validates a user-supplied team code against the
    league roster, raising a clean SystemExit instead of letting an
    unknown/lowercase code fall through to a raw KeyError deep in the
    simulation or reporting code."""
    if team is None:
        return None
    normalized = team.upper()
    if normalized not in team_ratings.base:
        available = ", ".join(sorted(team_ratings.base))
        raise SystemExit(f"Unknown team '{team}' for league '{league_key}'. Available: {available}")
    return normalized


def cmd_update(args: argparse.Namespace) -> None:
    league_config = _load_league(args.league)
    team_ratings = _team_ratings(league_config, args.seed)
    team = _normalize_team(team_ratings, args.team, args.league)
    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=args.games_per_team, seed=args.seed)

    result = run_monte_carlo(
        league_config,
        team_ratings.effective_ratings(),
        schedule,
        n_sims=args.sims,
        seed=args.seed,
    )
    payload = build_update(args.league.upper(), result, team=team)
    print(json.dumps(payload, indent=2))


def cmd_explain_injury(args: argparse.Namespace) -> None:
    league_config = _load_league(args.league)
    team_ratings = _team_ratings(league_config, args.seed)
    team = _normalize_team(team_ratings, args.team, args.league)
    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=args.games_per_team, seed=args.seed)

    event = injury(team, args.value, ramp_games=args.ramp, games_elapsed=args.elapsed)
    report, _ = measure_event_impact(league_config, team_ratings, schedule, None, event, n_sims=args.sims, seed=args.seed)
    print(json.dumps(report.as_dict(), indent=2))


def cmd_explain_trade(args: argparse.Namespace) -> None:
    league_config = _load_league(args.league)
    team_ratings = _team_ratings(league_config, args.seed)
    team_in = _normalize_team(team_ratings, args.team_in, args.league)
    team_out = _normalize_team(team_ratings, args.team_out, args.league)
    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=args.games_per_team, seed=args.seed)

    gaining_event = trade_leg(team_in, abs(args.value), ramp_games=args.ramp)
    losing_event = trade_leg(team_out, -abs(args.value), ramp_games=args.ramp)

    before = run_monte_carlo(league_config, team_ratings.effective_ratings(), schedule, n_sims=args.sims, seed=args.seed)
    team_ratings.apply_event(gaining_event)
    team_ratings.apply_event(losing_event)
    after = run_monte_carlo(league_config, team_ratings.effective_ratings(), schedule, n_sims=args.sims, seed=args.seed)

    print(
        json.dumps(
            {
                "team_in": {
                    "team": team_in,
                    "championship_probability_before": round(before.teams[team_in].championship_probability, 4),
                    "championship_probability_after": round(after.teams[team_in].championship_probability, 4),
                },
                "team_out": {
                    "team": team_out,
                    "championship_probability_before": round(before.teams[team_out].championship_probability, 4),
                    "championship_probability_after": round(after.teams[team_out].championship_probability, 4),
                },
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simulator", description="Live Season Simulator (Phase 1 MVP, mock data)")
    parser.add_argument("--league", default="nba", help="League key, e.g. nba")
    parser.add_argument("--sims", type=int, default=1000, help="Monte Carlo sample size (default 1000, per PRD P0.2)")
    parser.add_argument("--seed", type=int, default=2026, help="RNG seed for reproducible mock data + simulation")
    parser.add_argument("--games-per-team", type=int, default=20, help="Mock remaining games per team")
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="Today's update: championship odds (P0.6)")
    p_update.add_argument("--team", default=None, help="Scope to one team, e.g. BOS")
    p_update.set_defaults(func=cmd_update)

    p_injury = sub.add_parser("explain-injury", help="Apply a mock injury and show odds movement (P0.3 / P1.4)")
    p_injury.add_argument("--team", required=True)
    p_injury.add_argument("--value", type=float, required=True, help="Estimated win-share value lost (Elo points)")
    p_injury.add_argument("--ramp", type=int, default=0, help="Games for the effect to ramp in (0 = immediate)")
    p_injury.add_argument("--elapsed", type=int, default=0, help="Games already elapsed since the injury")
    p_injury.set_defaults(func=cmd_explain_injury)

    p_trade = sub.add_parser("explain-trade", help="Apply a mock trade and show odds movement for both sides (P0.3 / P1.4)")
    p_trade.add_argument("--team-in", required=True, help="Team receiving the traded value")
    p_trade.add_argument("--team-out", required=True, help="Team giving up the traded value")
    p_trade.add_argument("--value", type=float, required=True, help="Net Elo-point value of the traded player(s)")
    p_trade.add_argument("--ramp", type=int, default=5, help="Games for the effect to ramp in")
    p_trade.set_defaults(func=cmd_explain_trade)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
