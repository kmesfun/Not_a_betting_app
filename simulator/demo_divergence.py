"""End-to-end walkthrough of the divergence pipeline, on mock data.

Runs entirely offline: no API keys, no network. Uses the existing simulator
(mock_data + run_monte_carlo) and the new markets/divergence/parlay/ingest
modules to show what the product actually produces today.

    python demo_divergence.py
"""

from datetime import date, datetime, timezone

from simulator.divergence import AlertRule, DigestState, build_digest, detect, render_digest
from simulator.ingest.news import KeywordClassifier, NewsItem, ReviewPolicy, extract
from simulator.leagues.nba import LEAGUE, all_teams
from simulator.markets.base import MarketQuote
from simulator.markets.normalize import DevigMethod, devig
from simulator.mock_data import mock_remaining_schedule, mock_seed_ratings
from simulator.parlay import Leg, build_parlays
from simulator.ratings import TeamRatings
from simulator.simulate import run_monte_carlo

N_SIMS = 4000
RULE = "─" * 74


def header(title: str) -> None:
    print(f"\n{RULE}\n  {title}\n{RULE}")


def odds_table(result, limit: int = 6) -> None:
    print(f"  {'team':<6} {'title':>8} {'±SE':>8} {'conf':>8} {'playoffs':>9}  flag")
    for t in result.sorted_by_championship()[:limit]:
        flag = "low confidence" if t.low_confidence else ""
        print(f"  {t.team:<6} {t.championship_probability:>7.2%} "
              f"{t.championship_standard_error:>8.3%} "
              f"{t.conference_probability:>7.1%} "
              f"{t.playoff_probability:>8.1%}  {flag}")


def main() -> None:
    teams = all_teams()
    ratings = TeamRatings(base=mock_seed_ratings(teams))
    schedule = mock_remaining_schedule(teams, games_per_team=20)

    print(f"\n  NBA · {len(teams)} teams · {len(schedule)} games remaining · "
          f"{N_SIMS:,} simulations")

    # ── 1. Baseline ────────────────────────────────────────────────────────
    header("1. Championship odds, before any news")
    before = run_monte_carlo(LEAGUE, ratings.effective_ratings(), schedule,
                             n_sims=N_SIMS, seed=2026)
    odds_table(before)

    # ── 2. A wire report arrives ───────────────────────────────────────────
    favourite = before.sorted_by_championship()[0].team
    report = NewsItem(
        text=f"{favourite} star forward tore his ACL in the fourth quarter "
             f"and is out for the season, the team announced.",
        published=date(2026, 1, 15),
        source="wire",
    )

    header("2. An injury report comes in as prose")
    print(f'  "{report.text}"\n')

    # KeywordClassifier runs offline. It is deliberately mid-confidence, so
    # under the default policy it lands in review rather than moving odds.
    result = extract(report, KeywordClassifier(), team=favourite)
    c = result.classification
    print(f"  model read it as:   {c.event_type} / {c.availability} / {c.role}")
    print(f"  confidence:         {c.min_confidence:.2f}   confirmed: {c.is_confirmed:.2f}")
    print(f"  → status: {result.status.upper()}  ({result.reason})")
    print("\n  Nothing has moved yet. Keyword matching is not a confident judgment,")
    print("  so it queues for a human rather than repricing the board.")

    # With the real TypeSafe model the same report comes back high-confidence.
    print("\n  Re-running with the confidence TypeSafe's model would return:")
    confident = type(c)(
        event_type=c.event_type, availability=c.availability, role=c.role,
        player_name="star forward", team=favourite,
        event_confidence=0.97, availability_confidence=0.96,
        role_confidence=0.94, is_confirmed=0.98,
    )

    class _Fixed:
        def classify(self, item):
            return confident

    applied = extract(report, _Fixed(), team=favourite)
    print(f"  → status: {applied.status.upper()}  ({applied.reason})")
    ev = applied.event
    print(f"  → RosterEvent: {ev.team}  {ev.value_delta:+.0f} Elo  "
          f"ramp {ev.ramp_games} games  [{ev.label}]")
    print("\n  The magnitude came from ELO_DELTA_TABLE, not from the model.")
    print("  The model chose labels; code chose the number.")

    # ── 3. Re-simulate ─────────────────────────────────────────────────────
    ratings.apply_event(ev)
    after = run_monte_carlo(LEAGUE, ratings.effective_ratings(), schedule,
                            n_sims=N_SIMS, seed=2026)

    header("3. Championship odds, re-simulated")
    odds_table(after)
    moved = (after.teams[favourite].championship_probability
             - before.teams[favourite].championship_probability)
    print(f"\n  {favourite}: {before.teams[favourite].championship_probability:.2%}"
          f" → {after.teams[favourite].championship_probability:.2%}  ({moved:+.2%})")

    # ── 4. The market hasn't caught up ─────────────────────────────────────
    top = [t.team for t in before.sorted_by_championship()[:8]]
    now = datetime.now(timezone.utc)
    # Kalshi is still quoting the pre-injury board, plus a typical overround.
    quotes = [
        MarketQuote(venue="kalshi", market_id=f"NBACHAMP-{t}", outcome=t,
                    price=before.teams[t].championship_probability * 1.10, as_of=now)
        for t in top
    ]

    header("4. Model vs market")
    raw = {q.outcome: q.price for q in quotes}
    fair = devig(raw, method=DevigMethod.POWER)
    print(f"  Raw Kalshi prices sum to {sum(raw.values()):.3f} — "
          f"a {fair.overround:.1%} overround.")
    print("  Devigged before comparing, or every outcome would look mispriced\n"
          "  in the same direction and we would ship a bias as a signal.\n")

    model = {t: after.teams[t].championship_probability for t in top}
    errors = {t: after.teams[t].championship_standard_error for t in top}
    divergences = detect(model, errors, quotes)

    print(f"  {'team':<6} {'model':>8} {'market':>8} {'gap':>8} {'z':>7}")
    for d in divergences[:6]:
        print(f"  {d.outcome:<6} {d.model_probability:>7.2%} "
              f"{d.market_probability:>7.2%} {d.delta_points:>+7.1f}pt "
              f"{d.z_score:>+6.1f}")

    # ── 5. The digest ──────────────────────────────────────────────────────
    header("5. What gets pushed")
    state = DigestState()
    items = build_digest(divergences, AlertRule(), state)
    body = render_digest(items)
    print("  " + (body.replace("\n", "\n  ") if body else
                  "(nothing — correct behaviour on a quiet day)"))

    print("\n  Same digest, run again five minutes later:")
    repeat = build_digest(divergences, AlertRule(), state)
    print(f"  → {len(repeat)} items. A standing gap is not news twice.")

    # ── 6. Parlays ─────────────────────────────────────────────────────────
    header("6. Risk-tiered parlays")
    legs = []
    for t in after.sorted_by_championship()[:16]:
        for label, p in (("make the playoffs", t.playoff_probability),
                         ("win their conference", t.conference_probability)):
            if 0.03 < p < 0.93:
                legs.append(Leg(
                    id=f"{t.team}-{label[:4]}",
                    description=f"{t.team} {label}",
                    probability=p,
                    standard_error=(p * (1 - p) / N_SIMS) ** 0.5,
                    # Team is a correlation key, so no parlay can ever contain
                    # the same franchise twice.
                    correlation_keys=frozenset({f"team:{t.team}"}),
                ))

    for parlay in build_parlays(legs):
        print(f"\n  {parlay.describe()}")
        print(f"     ±{parlay.relative_error:.1%} relative error at {N_SIMS:,} sims")

    print("\n  Analysis and entertainment only. Not betting advice.\n")


if __name__ == "__main__":
    main()
