from datetime import datetime, timezone

import pytest

from simulator.divergence import (
    AlertRule,
    DigestState,
    Divergence,
    build_digest,
    detect,
    render_digest,
)
from simulator.markets.base import MarketQuote


def quote(venue, outcome, price):
    return MarketQuote(
        venue=venue, market_id=f"{venue}-{outcome}", outcome=outcome,
        price=price, as_of=datetime.now(timezone.utc),
    )


def divergence(outcome="Nuggets", model=0.20, se=0.002, market=0.12):
    return Divergence(
        outcome=outcome, model_probability=model, model_se=se,
        market_probability=market, venue_probabilities={"kalshi": market},
        as_of=datetime.now(timezone.utc),
    )


class TestDivergenceMath:
    def test_positive_delta_means_undervalued(self):
        d = divergence(model=0.20, market=0.12)
        assert d.delta == pytest.approx(0.08)
        assert d.direction == "undervalued"

    def test_negative_delta_means_overvalued(self):
        d = divergence(model=0.10, market=0.18)
        assert d.direction == "overvalued"

    def test_z_score_scales_with_uncertainty(self):
        tight = divergence(model=0.20, market=0.17, se=0.002)
        loose = divergence(model=0.20, market=0.17, se=0.015)
        assert abs(tight.z_score) > abs(loose.z_score)

    def test_zero_se_does_not_divide_by_zero(self):
        z = divergence(model=0.0001, market=0.40, se=0.0).z_score
        assert z == pytest.approx(-99.9)

    def test_z_score_is_capped_at_a_readable_magnitude(self):
        # Regression: a near-zero model probability collapsed the standard
        # error and produced z = -8,119 in the digest.
        z = divergence(model=0.00002, market=0.398, se=0.0000001).z_score
        assert abs(z) <= 99.9

    def test_cap_does_not_distort_ordinary_gaps(self):
        z = divergence(model=0.20, market=0.12, se=0.002).z_score
        assert z == pytest.approx(40.0, rel=0.01)

    def test_describe_mentions_both_sides(self):
        text = divergence().describe()
        assert "model" in text.lower() and "kalshi" in text.lower()

    def test_delta_points_are_percentage_points(self):
        # Regression: delta is a fraction, so displaying it directly as "pts"
        # rendered every gap as "0.0pts".
        d = divergence(model=0.20, market=0.12)
        assert d.delta_points == pytest.approx(8.0)

    def test_describe_shows_a_nonzero_gap(self):
        text = divergence(model=0.20, market=0.12).describe()
        assert "8.0pts" in text
        assert "0.0pts" not in text


class TestDetection:
    def test_devigs_before_comparing(self):
        # Market sums to 1.20; without devigging every outcome looks too high
        # and the model would appear systematically "undervalued" everywhere.
        quotes = [
            quote("kalshi", "A", 0.60),
            quote("kalshi", "B", 0.36),
            quote("kalshi", "C", 0.24),
        ]
        model = {"A": 0.50, "B": 0.30, "C": 0.20}
        se = {k: 0.002 for k in model}
        results = detect(model, se, quotes)

        # Post-devig the market sums to 1, so deltas cannot all share a sign.
        signs = {d.delta > 0 for d in results}
        assert len(signs) == 2, "devigging should not leave a one-sided bias"

    def test_averages_across_venues(self):
        quotes = [
            quote("kalshi", "A", 0.50), quote("kalshi", "B", 0.50),
            quote("polymarket", "A", 0.30), quote("polymarket", "B", 0.70),
        ]
        results = detect({"A": 0.4, "B": 0.6}, {"A": 0.002, "B": 0.002}, quotes)
        a = next(d for d in results if d.outcome == "A")
        assert a.market_probability == pytest.approx(0.40, abs=0.01)
        assert set(a.venue_probabilities) == {"kalshi", "polymarket"}

    def test_sorted_by_gap_size(self):
        quotes = [
            quote("kalshi", "A", 0.50), quote("kalshi", "B", 0.30), quote("kalshi", "C", 0.20),
        ]
        model = {"A": 0.50, "B": 0.10, "C": 0.40}
        results = detect(model, {k: 0.002 for k in model}, quotes)
        gaps = [abs(d.delta) for d in results]
        assert gaps == sorted(gaps, reverse=True)

    def test_skips_outcomes_with_no_market(self):
        quotes = [quote("kalshi", "A", 0.5), quote("kalshi", "B", 0.5)]
        results = detect({"A": 0.4, "B": 0.4, "NoMarket": 0.2},
                         {"A": 0.002, "B": 0.002, "NoMarket": 0.002}, quotes)
        assert {d.outcome for d in results} == {"A", "B"}

    def test_no_quotes_returns_empty(self):
        assert detect({"A": 0.5}, {"A": 0.01}, []) == []


class TestAlerting:
    def test_small_gap_does_not_qualify(self):
        rule = AlertRule()
        assert not rule.qualifies(divergence(model=0.121, market=0.12))

    def test_large_confident_gap_qualifies(self):
        rule = AlertRule()
        assert rule.qualifies(divergence(model=0.20, market=0.12, se=0.002))

    def test_large_but_noisy_gap_does_not_qualify(self):
        # Same 8pt gap, but the model is too uncertain to call it.
        rule = AlertRule()
        assert not rule.qualifies(divergence(model=0.20, market=0.12, se=0.06))

    def test_illiquid_market_filtered_out(self):
        rule = AlertRule(min_market_probability=0.01)
        assert not rule.qualifies(divergence(model=0.05, market=0.001, se=0.001))


class TestDigest:
    def test_quiet_day_sends_nothing(self):
        """The most important behaviour in the module (PRD P0.9)."""
        state = DigestState()
        boring = [divergence(model=0.121, market=0.12)]
        assert build_digest(boring, AlertRule(), state) == []
        assert render_digest([]) == ""

    def test_new_divergence_fires(self):
        state = DigestState()
        items = build_digest([divergence()], AlertRule(), state)
        assert len(items) == 1

    def test_same_gap_does_not_refire(self):
        state = DigestState()
        d = divergence()
        assert len(build_digest([d], AlertRule(), state)) == 1
        assert build_digest([d], AlertRule(), state) == [], "standing gap re-alerted"

    def test_materially_changed_gap_refires(self):
        state = DigestState()
        build_digest([divergence(model=0.20, market=0.12)], AlertRule(), state)
        widened = divergence(model=0.26, market=0.12)
        assert len(build_digest([widened], AlertRule(), state)) == 1

    def test_respects_max_items(self):
        state = DigestState()
        many = [divergence(outcome=f"T{i}", model=0.20 + i * 0.01) for i in range(12)]
        assert len(build_digest(many, AlertRule(), state, max_items=3)) == 3

    def test_crowded_out_gaps_do_not_resurface_as_news(self):
        """Regression: gaps beyond max_items were never recorded as seen, so
        they fired the next day as if new — a quiet day would still produce a
        digest of yesterday's leftovers."""
        state = DigestState()
        many = [divergence(outcome=f"T{i}", model=0.20 + i * 0.01) for i in range(8)]

        first = build_digest(many, AlertRule(), state, max_items=3)
        assert len(first) == 3

        second = build_digest(many, AlertRule(), state, max_items=3)
        assert second == [], "crowded-out gaps leaked into the next digest"

    def test_slow_drift_still_eventually_fires(self):
        """A gap that widens gradually should not be suppressed forever by
        having its baseline refreshed on every run.

        Step sizes are kept clear of the 0.02 rearm threshold on purpose:
        values landing exactly on it make the result depend on float error
        (0.22 - 0.12 is 0.0999...), which is a fine outcome in production —
        the alert simply fires a day later — but makes for a flaky test.
        """
        rule = AlertRule()
        state = DigestState()
        build_digest([divergence(model=0.20, market=0.12)], rule, state)

        # Each step is comfortably below rearm_delta on its own.
        for model in (0.205, 0.21, 0.215):
            fired = build_digest([divergence(model=model, market=0.12)], rule, state)
            assert fired == [], "a sub-threshold step should not fire"

        # Accumulated drift is now well past the threshold.
        widened = divergence(model=0.26, market=0.12)
        assert len(build_digest([widened], rule, state)) == 1

    def test_rendered_digest_carries_disclaimer(self):
        body = render_digest([divergence()])
        assert "not betting advice" in body.lower()
