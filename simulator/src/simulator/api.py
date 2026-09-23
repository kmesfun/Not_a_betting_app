"""Callable interface, HTTP form (PRD P0.6), plus a small dashboard at "/"
that consumes it. Optional -- requires `fastapi` and `uvicorn` (see
requirements.txt); the CLI (cli.py) has no such dependency. Run with:
uvicorn simulator.api:app --reload

Known Phase 1 simplification: PRD P0.6's non-functional requirement calls
for serving from a precomputed batch (well under 1s response time), with
simulation running on a separate schedule. This MVP has no scheduler or
persistence layer yet (that's P0.1, blocked per PRD section 1a), so each
request runs the batch synchronously -- fine for local/demo use at
n_sims=1000, but the real behavior described in P0.6 still needs a
scheduled-batch-plus-cache layer in front of this before it's a legitimate
"daily" service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import FileResponse
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "api.py requires fastapi and uvicorn. Install with: pip install -r simulator/requirements.txt"
    ) from exc

from .divergence import AlertRule, DigestState, build_digest, detect, render_digest
from .events import injury, measure_event_impact, trade_leg
from .leagues import LEAGUES
from .markets.mock_market import DEFAULT_OVERROUND, quiet_market, stale_market
from .markets.normalize import DevigMethod, devig
from .mock_data import mock_remaining_schedule, mock_seed_ratings
from .ratings import TeamRatings
from .report import build_update
from .simulate import run_monte_carlo

app = FastAPI(
    title="Live Season Simulator (Phase 1 MVP)",
    description="Mock-data NBA Monte Carlo championship simulator. See docs/PRD.md.",
    version="0.1.0",
)

DEFAULT_SEED = 2026
DEFAULT_GAMES_PER_TEAM = 20
STATIC_DIR = Path(__file__).parent / "static"


def _load_league(league: str) -> tuple[str, dict]:
    league_key = league.lower()
    if league_key not in LEAGUES:
        raise HTTPException(status_code=404, detail=f"Unknown league '{league}'. Available: {', '.join(LEAGUES)}")
    return league_key, LEAGUES[league_key]


def _team_ratings(league_config: dict, seed: int) -> TeamRatings:
    teams = [t for roster in league_config["conferences"].values() for t in roster]
    return TeamRatings(base=mock_seed_ratings(teams, seed=seed))


def _validate_team(team_ratings: TeamRatings, team: str, league: str) -> str:
    team_upper = team.upper()
    if team_upper not in team_ratings.base:
        raise HTTPException(status_code=404, detail=f"Unknown team '{team}' in league '{league}'")
    return team_upper


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/v1/update")
def get_update(
    league: str = Query("nba"),
    team: str | None = Query(None),
    sims: int = Query(1000, ge=100, le=20000),
    seed: int = Query(DEFAULT_SEED),
    games_per_team: int = Query(DEFAULT_GAMES_PER_TEAM, ge=1, le=82),
) -> dict:
    league_key, league_config = _load_league(league)
    team_ratings = _team_ratings(league_config, seed)
    team_upper = _validate_team(team_ratings, team, league) if team else None

    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=games_per_team, seed=seed)
    result = run_monte_carlo(league_config, team_ratings.effective_ratings(), schedule, n_sims=sims, seed=seed)

    return build_update(league_key.upper(), result, team=team_upper)


@app.get("/v1/explain-injury")
def get_explain_injury(
    league: str = Query("nba"),
    team: str = Query(...),
    value: float = Query(..., ge=0, le=500, description="Estimated win-share value lost, in Elo points"),
    ramp_games: int = Query(3, ge=0, le=20),
    sims: int = Query(1000, ge=100, le=20000),
    seed: int = Query(DEFAULT_SEED),
    games_per_team: int = Query(DEFAULT_GAMES_PER_TEAM, ge=1, le=82),
) -> dict:
    """PRD P0.3 / P1.4: what-if impact of a player going out. Read-only --
    runs a before/after batch against the mock snapshot, doesn't persist
    anything (see the stateless-MVP note in cli.py)."""
    league_key, league_config = _load_league(league)
    team_ratings = _team_ratings(league_config, seed)
    team_upper = _validate_team(team_ratings, team, league)

    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=games_per_team, seed=seed)
    event = injury(team_upper, value, ramp_games=ramp_games)
    report, _ = measure_event_impact(league_config, team_ratings, schedule, None, event, n_sims=sims, seed=seed)
    return report.as_dict()


@app.get("/v1/explain-trade")
def get_explain_trade(
    league: str = Query("nba"),
    team_in: str = Query(..., description="Team acquiring the traded value"),
    team_out: str = Query(..., description="Team giving up the traded value"),
    value: float = Query(..., ge=0, le=500, description="Net Elo-point value of the trade"),
    ramp_games: int = Query(5, ge=0, le=20),
    sims: int = Query(1000, ge=100, le=20000),
    seed: int = Query(DEFAULT_SEED),
    games_per_team: int = Query(DEFAULT_GAMES_PER_TEAM, ge=1, le=82),
) -> dict:
    """PRD P0.3 / P1.4: what-if impact of a trade, for both sides."""
    league_key, league_config = _load_league(league)
    team_ratings = _team_ratings(league_config, seed)
    team_in_upper = _validate_team(team_ratings, team_in, league)
    team_out_upper = _validate_team(team_ratings, team_out, league)
    if team_in_upper == team_out_upper:
        raise HTTPException(status_code=400, detail="team_in and team_out must be different teams")

    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=games_per_team, seed=seed)

    before = run_monte_carlo(league_config, team_ratings.effective_ratings(), schedule, n_sims=sims, seed=seed)
    team_ratings.apply_event(trade_leg(team_in_upper, value, ramp_games=ramp_games))
    team_ratings.apply_event(trade_leg(team_out_upper, -value, ramp_games=ramp_games))
    after = run_monte_carlo(league_config, team_ratings.effective_ratings(), schedule, n_sims=sims, seed=seed)

    return {
        "team_in": {
            "team": team_in_upper,
            "championship_probability_before": round(before.teams[team_in_upper].championship_probability, 4),
            "championship_probability_after": round(after.teams[team_in_upper].championship_probability, 4),
        },
        "team_out": {
            "team": team_out_upper,
            "championship_probability_before": round(before.teams[team_out_upper].championship_probability, 4),
            "championship_probability_after": round(after.teams[team_out_upper].championship_probability, 4),
        },
    }


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/divergence")
def get_divergence(
    league: str = Query("nba"),
    team: str | None = Query(None, description="Team hit by a roster event; omit for a quiet day"),
    value: float = Query(110.0, ge=0, le=500, description="Elo points lost by that team"),
    top_n: int = Query(10, ge=2, le=30),
    sims: int = Query(1000, ge=100, le=20000),
    seed: int = Query(DEFAULT_SEED),
    games_per_team: int = Query(DEFAULT_GAMES_PER_TEAM, ge=1, le=82),
) -> dict:
    """Model vs market, and the digest that would be pushed.

    THE MARKET DATA HERE IS SYNTHETIC (markets/mock_market.py). The
    Polymarket and Kalshi clients exist and are unit-tested, but have not
    been run against live endpoints, and outcomes are not yet mapped to
    venue market IDs. Every response says so in `market_source` and the
    dashboard shows it; do not quietly present these numbers as real prices.

    Two scenarios:
      no `team`  - quiet day. The market broadly agrees, and the digest
                   should come back empty. That is correct behaviour, not a
                   failure: a digest that fires every day gets ignored.
      `team` set - that team has taken a hit, our model has repriced, and
                   the market is still quoting the pre-event board.
    """
    league_key, league_config = _load_league(league)
    team_ratings = _team_ratings(league_config, seed)
    teams = list(team_ratings.base)
    schedule = mock_remaining_schedule(teams, games_per_team=games_per_team, seed=seed)

    before = run_monte_carlo(
        league_config, team_ratings.effective_ratings(), schedule, n_sims=sims, seed=seed
    )

    if team:
        team_upper = _validate_team(team_ratings, team, league)
        team_ratings.apply_event(injury(team_upper, value, ramp_games=0))
        after = run_monte_carlo(
            league_config, team_ratings.effective_ratings(), schedule, n_sims=sims, seed=seed
        )
        quotes = stale_market(before)
        scenario = "stale"
    else:
        team_upper = None
        after = before
        quotes = quiet_market(before, seed=seed)
        scenario = "quiet"

    priced = [q.outcome for q in quotes]
    model = {t: after.teams[t].championship_probability for t in priced}
    errors = {t: after.teams[t].championship_standard_error for t in priced}

    raw_total = sum(q.price for q in quotes)
    # Devig across the complete field, THEN slice to the teams worth showing.
    # Slicing first would hand devig a partial book (see IncompleteBookError).
    divergences = detect(model, errors, quotes)[:top_n]

    state = DigestState()
    pushed = build_digest(divergences, AlertRule(), state)

    return {
        "league": league_key.upper(),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "n_sims": after.n_sims,
        "scenario": scenario,
        "event_team": team_upper,
        "event_value_elo": value if team_upper else None,
        "market_source": "mock — synthetic prices, not live Polymarket/Kalshi",
        "overround": round(raw_total - 1.0, 4),
        "devig_method": DevigMethod.POWER.value,
        "divergences": [
            {
                "team": d.outcome,
                "model": round(d.model_probability, 4),
                "model_se": round(d.model_se, 4),
                "market": round(d.market_probability, 4),
                "delta_points": round(d.delta_points, 2),
                "z_score": round(d.z_score, 1),
                "direction": d.direction,
                "alerted": any(p.outcome == d.outcome for p in pushed),
            }
            for d in divergences
        ],
        "digest": {
            "send": bool(pushed),
            "count": len(pushed),
            "body": render_digest(pushed),
        },
        "disclaimer": "Analysis and entertainment only. Not betting advice.",
    }
