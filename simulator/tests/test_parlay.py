import pytest

from simulator.parlay import (
    DEFAULT_TIERS,
    Leg,
    Parlay,
    Tier,
    build_parlays,
    explain_precision_requirement,
)


def leg(id_, p, se=None, keys=()):
    return Leg(
        id=id_, description=f"leg {id_}", probability=p,
        standard_error=se if se is not None else (p * (1 - p) / 50_000) ** 0.5,
        correlation_keys=frozenset(keys),
    )


class TestLeg:
    def test_rejects_impossible_probability(self):
        with pytest.raises(ValueError, match="probability must be"):
            leg("x", 1.0)
        with pytest.raises(ValueError, match="probability must be"):
            leg("x", 0.0)

    def test_rejects_negative_error(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            Leg(id="x", description="d", probability=0.5, standard_error=-0.1)

    def test_shared_key_is_a_conflict(self):
        a = leg("a", 0.6, keys={"game:BOS@NYK"})
        b = leg("b", 0.7, keys={"game:BOS@NYK"})
        assert a.conflicts_with(b)

    def test_unrelated_legs_do_not_conflict(self):
        assert not leg("a", 0.6, keys={"game:1"}).conflicts_with(leg("b", 0.7, keys={"game:2"}))


class TestParlayMath:
    def test_probability_is_the_product(self):
        p = Parlay(tier="t", legs=(leg("a", 0.5), leg("b", 0.4)))
        assert p.probability == pytest.approx(0.20)

    def test_error_compounds_across_legs(self):
        one = Parlay(tier="t", legs=(leg("a", 0.5),))
        four = Parlay(tier="t", legs=(leg("a", 0.5), leg("b", 0.5), leg("c", 0.5), leg("d", 0.5)))
        assert four.relative_error > one.relative_error

    def test_more_sims_narrow_the_odds_range(self):
        """The PRD 9.4 finding, enforced as a test."""
        def build(n):
            legs = tuple(
                Leg(id=str(i), description="l", probability=p,
                    standard_error=(p * (1 - p) / n) ** 0.5)
                for i, p in enumerate([0.25, 0.20, 0.15, 0.10])
            )
            return Parlay(tier="Long shot", legs=legs)

        thousand = build(1_000)
        fifty_k = build(50_000)

        assert thousand.relative_error > 0.10, "1k sims should be visibly imprecise"
        assert fifty_k.relative_error < 0.03, "50k sims should be tight"

        lo_1k, hi_1k = thousand.odds_range
        lo_50k, hi_50k = fifty_k.odds_range
        assert (hi_1k - lo_1k) > (hi_50k - lo_50k) * 5

    def test_consistency_check_catches_correlation(self):
        bad = Parlay(tier="t", legs=(
            leg("a", 0.6, keys={"team:BOS"}),
            leg("b", 0.5, keys={"team:BOS"}),
        ))
        assert not bad.is_internally_consistent()

    def test_longshot_describe_shows_odds(self):
        p = Parlay(tier="Long shot", legs=(
            leg("a", 0.2, se=0.02), leg("b", 0.15, se=0.02),
            leg("c", 0.1, se=0.02), leg("d", 0.1, se=0.02),
        ))
        text = p.describe()
        assert "1 in" in text and "–" in text

    def test_safe_parlay_omits_meaningless_odds(self):
        # Regression: a 73% parlay rendered as "1 in 1–1".
        p = Parlay(tier="Safe", legs=(leg("a", 0.85), leg("b", 0.86)))
        text = p.describe()
        assert "1 in" not in text
        assert "73" in text


class TestBuilder:
    @pytest.fixture
    def pool(self):
        return [
            leg("a", 0.82, keys={"game:1"}),
            leg("b", 0.78, keys={"game:2"}),
            leg("c", 0.71, keys={"game:3"}),
            leg("d", 0.60, keys={"game:4"}),
            leg("e", 0.55, keys={"game:5"}),
            leg("f", 0.48, keys={"game:6"}),
            leg("g", 0.33, keys={"game:7"}),
            leg("h", 0.25, keys={"game:8"}),
            leg("i", 0.18, keys={"game:9"}),
            leg("j", 0.12, keys={"game:10"}),
        ]

    def test_builds_something_for_each_tier(self, pool):
        parlays = build_parlays(pool)
        assert {p.tier for p in parlays} == {t.name for t in DEFAULT_TIERS}

    def test_every_parlay_is_correlation_free(self, pool):
        for p in build_parlays(pool):
            assert p.is_internally_consistent()

    def test_never_combines_correlated_legs(self):
        # Every leg is from the same game, so nothing can legally be combined.
        same_game = [leg(str(i), 0.5 + i * 0.05, keys={"game:BOS@NYK"}) for i in range(6)]
        assert build_parlays(same_game) == []

    def test_parlays_land_inside_their_tier_band(self, pool):
        by_name = {t.name: t for t in DEFAULT_TIERS}
        for p in build_parlays(pool):
            tier = by_name[p.tier]
            assert tier.min_probability <= p.probability < tier.max_probability

    def test_tiers_are_actually_distinct(self, pool):
        """Guards the PRD Section 10 concern about clustered tiers."""
        parlays = {p.tier: p.probability for p in build_parlays(pool)}
        assert parlays["Safe"] > parlays["Balanced"] > parlays["Long shot"]

    def test_leg_counts_respect_tier_limits(self, pool):
        by_name = {t.name: t for t in DEFAULT_TIERS}
        for p in build_parlays(pool):
            tier = by_name[p.tier]
            assert tier.min_legs <= len(p.legs) <= tier.max_legs

    def test_imprecise_legs_are_rejected(self, pool):
        """A tier refuses combinations it cannot state precisely enough."""
        noisy = [
            Leg(id=l.id, description=l.description, probability=l.probability,
                standard_error=l.probability * 0.25, correlation_keys=l.correlation_keys)
            for l in pool
        ]
        strict = (Tier("Strict", 0.0, 1.0, 2, 3, max_relative_error=0.01),)
        assert build_parlays(noisy, tiers=strict) == []

    def test_empty_pool_is_handled(self):
        assert build_parlays([]) == []


def test_precision_explainer_is_readable():
    text = explain_precision_requirement([leg("a", 0.2), leg("b", 0.15)])
    assert "1 in" in text and "%" in text
