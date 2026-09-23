"""Tests for news extraction — with the model/code boundary as the centrepiece.

The boundary tests below are the reason this module is safe to use. If someone
later "simplifies" news.py by letting a model confidence scale an Elo
delta, these fail loudly.
"""

from datetime import date

import pytest

from simulator.ingest.news import (
    AVAILABILITY,
    EVENT_TYPES,
    RAMP_GAMES,
    ROLES,
    ELO_DELTA_TABLE,
    Classification,
    Classifier,
    KeywordClassifier,
    NewsItem,
    ReviewPolicy,
    TypeSafeClassifier,
    extract,
    to_roster_event,
    elo_delta,
)
from simulator.ratings import RosterEvent


def item(text: str, published: date | None = None) -> NewsItem:
    return NewsItem(text=text, published=published or date(2026, 11, 3), source="test")


def classification(
    event_type="injury",
    availability="out_season",
    role="franchise",
    conf=0.97,
    confirmed=0.95,
) -> Classification:
    return Classification(
        event_type=event_type,
        availability=availability,
        role=role,
        player_name="A. Player",
        team="PHX",
        event_confidence=conf,
        availability_confidence=conf,
        role_confidence=conf,
        is_confirmed=confirmed,
    )


# ─────────────────────────────────────────────────────────────────────────────
# THE BOUNDARY. These are the important tests in this file.
# ─────────────────────────────────────────────────────────────────────────────


class TestModelCodeBoundary:
    def test_confidence_never_changes_the_magnitude(self):
        """The core guarantee: identical labels, wildly different confidences,
        identical Elo delta. Confidence gates whether we act; it is never
        arithmetic input."""
        timid = classification(conf=0.51, confirmed=0.76)
        certain = classification(conf=1.00, confirmed=1.00)

        a = to_roster_event(timid, "BOS")
        b = to_roster_event(certain, "BOS")

        assert a.value_delta == b.value_delta

    def test_magnitude_comes_only_from_the_table(self):
        """Every producible delta is a table value (or its negation for returns),
        so no computed or model-derived number can leak in."""
        allowed = set(ELO_DELTA_TABLE.values())
        allowed |= {-v for v in ELO_DELTA_TABLE.values()}

        for role in ROLES:
            for availability in AVAILABILITY:
                for event_type in EVENT_TYPES:
                    if event_type == "unrelated":
                        continue
                    assert elo_delta(role, availability, event_type) in allowed

    def test_lookup_is_a_pure_function(self):
        for _ in range(5):
            assert elo_delta("starter", "out_multiweek", "injury") == -20.0

    def test_unknown_label_pair_raises_rather_than_defaulting(self):
        """A silent zero is an event that quietly does nothing — far worse than
        a crash, because nobody notices it."""
        with pytest.raises(KeyError, match="no Elo entry"):
            elo_delta("superstar", "out_season", "injury")

    def test_every_label_combination_is_covered(self):
        """No gap in the table, so a valid classification can never hit the
        KeyError path in production."""
        for role in ROLES:
            for availability in AVAILABILITY:
                assert (role, availability) in ELO_DELTA_TABLE

    def test_classification_carries_no_magnitude_field(self):
        """Structural guard: if someone adds a model-supplied magnitude to
        Classification, this fails and they have to think about it."""
        fields = set(Classification.__dataclass_fields__)
        forbidden = {"value_delta", "elo_delta", "magnitude", "impact", "rating_delta"}
        assert not (fields & forbidden), (
            f"Classification must not carry magnitudes: {fields & forbidden}"
        )

    def test_roster_event_magnitude_is_reproducible_across_runs(self):
        """Same inputs, same event — which is what makes backtesting honest."""
        c = classification()
        events = [to_roster_event(c, "DEN") for _ in range(3)]
        assert len({e.value_delta for e in events}) == 1
        assert len({e.ramp_games for e in events}) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Magnitudes and direction
# ─────────────────────────────────────────────────────────────────────────────


class TestMagnitudes:
    def test_more_important_players_cost_more(self):
        deltas = [elo_delta(r, "out_season", "injury") for r in ROLES]
        assert deltas == sorted(deltas, reverse=True), "depth should hurt least"
        assert deltas[-1] < deltas[0]

    def test_longer_absence_costs_more(self):
        order = ["available", "questionable", "out_short", "out_multiweek", "out_season"]
        deltas = [elo_delta("franchise", a, "injury") for a in order]
        assert deltas == sorted(deltas, reverse=True)

    def test_injury_is_negative_return_is_positive(self):
        assert elo_delta("franchise", "out_season", "injury") < 0
        assert elo_delta("franchise", "out_season", "return") > 0

    def test_return_exactly_mirrors_the_injury(self):
        out = elo_delta("starter", "out_multiweek", "injury")
        back = elo_delta("starter", "out_multiweek", "return")
        assert back == -out

    def test_available_player_moves_nothing(self):
        assert elo_delta("franchise", "available", "injury") == 0.0


class TestRosterEventConstruction:
    def test_injury_applies_immediately(self):
        e = to_roster_event(classification(event_type="injury"), "BOS")
        assert e.ramp_games == 0, "a player who is out is out"

    def test_acquisitions_ramp(self):
        for event_type in ("trade", "signing", "return"):
            e = to_roster_event(
                classification(event_type=event_type, availability="available"),
                "BOS",
            )
            assert e.ramp_games == RAMP_GAMES[event_type] > 0

    def test_produces_a_real_roster_event(self):
        e = to_roster_event(classification(), "PHX")
        assert isinstance(e, RosterEvent)
        assert e.team == "PHX"
        # and it composes with the ratings layer: an injury has no ramp, so its
        # full effect applies immediately
        assert e.ramp_games == 0
        assert e.current_effect() == pytest.approx(e.value_delta)

    def test_description_is_human_readable(self):
        e = to_roster_event(classification(), "BOS")
        assert "injury" in e.label and "out_season" in e.label


# ─────────────────────────────────────────────────────────────────────────────
# Confidence gating
# ─────────────────────────────────────────────────────────────────────────────


class TestConfidenceGating:
    def test_confident_confirmed_report_is_applied(self):
        r = extract(item("Star out for the season"), _fixed(classification()), team="BOS")
        assert r.status == "applied"
        assert r.event is not None

    def test_uncertain_report_goes_to_review_not_into_the_odds(self):
        r = extract(item("x"), _fixed(classification(conf=0.72)), team="BOS")
        assert r.status == "needs_review"
        assert r.event is None, "an unreviewed event must never reach the simulator"

    def test_unreadable_report_is_discarded(self):
        r = extract(item("x"), _fixed(classification(conf=0.2)), team="BOS")
        assert r.status == "discarded"
        assert r.event is None

    def test_unconfirmed_report_is_held(self):
        """'Could miss time' must not move published odds."""
        r = extract(item("x"), _fixed(classification(confirmed=0.4)), team="BOS")
        assert r.status == "needs_review"
        assert r.event is None

    def test_unrelated_news_produces_nothing(self):
        r = extract(item("x"), _fixed(classification(event_type="unrelated")), team="BOS")
        assert r.status == "unrelated"
        assert r.event is None

    def test_unmapped_team_is_held_not_guessed(self):
        unmapped = Classification(
            event_type="injury", availability="out_season", role="franchise",
            player_name="A. Player", team=None,
            event_confidence=0.97, availability_confidence=0.97,
            role_confidence=0.97, is_confirmed=0.95,
        )
        r = extract(item("x"), _fixed(unmapped), team=None)
        assert r.status == "needs_review"
        assert r.event is None

    def test_weakest_judgment_governs(self):
        c = Classification(
            event_type="injury", availability="out_season", role="franchise",
            player_name=None, team=None,
            event_confidence=0.99, availability_confidence=0.55, role_confidence=0.99,
            is_confirmed=0.99,
        )
        assert c.min_confidence == pytest.approx(0.55)
        assert extract(item("x"), _fixed(c), team="BOS").status == "needs_review"

    def test_stricter_policy_holds_more(self):
        c = classification(conf=0.93)
        assert extract(item("x"), _fixed(c), "BOS").status == "applied"
        strict = ReviewPolicy(auto_apply_above=0.98)
        assert extract(item("x"), _fixed(c), "BOS", strict).status == "needs_review"

    def test_every_non_applied_outcome_has_a_reason(self):
        for c in (classification(conf=0.2), classification(conf=0.7),
                  classification(confirmed=0.3), classification(event_type="unrelated")):
            r = extract(item("x"), _fixed(c), team="BOS")
            assert r.reason, "a held report must say why"


# ─────────────────────────────────────────────────────────────────────────────
# Classifiers
# ─────────────────────────────────────────────────────────────────────────────


class TestKeywordClassifier:
    @pytest.fixture
    def clf(self):
        return KeywordClassifier()

    def test_detects_season_ending_injury(self, clf):
        c = clf.classify(item("Star guard tore his ACL, out for the season"))
        assert c.event_type == "injury"
        assert c.availability == "out_season"
        assert c.role == "franchise"

    def test_detects_a_trade(self, clf):
        c = clf.classify(item("Suns acquired the forward in exchange for two picks"))
        assert c.event_type == "trade"

    def test_detects_a_return(self, clf):
        c = clf.classify(item("Starting quarterback cleared to play Sunday"))
        assert c.event_type == "return"
        assert c.availability == "available"

    def test_ignores_unrelated_news(self, clf):
        c = clf.classify(item("The team unveiled new alternate jerseys"))
        assert c.event_type == "unrelated"

    def test_hedged_language_lowers_confirmation(self, clf):
        hedged = clf.classify(item("Star could miss time, reportedly day-to-day"))
        firm = clf.classify(item("Star is day-to-day"))
        assert hedged.is_confirmed < firm.is_confirmed

    def test_output_is_never_auto_applied(self, clf):
        """Keyword matching is a fallback, not a judgment — under default policy
        its output always lands in review rather than moving odds unseen."""
        c = clf.classify(item("Star guard tore his ACL, out for the season"))
        assert extract(item("..."), _fixed(c), team="BOS").status == "needs_review"

    def test_satisfies_the_classifier_protocol(self, clf):
        assert isinstance(clf, Classifier)

    def test_is_deterministic(self, clf):
        text = "Star guard tore his ACL, out for the season"
        assert clf.classify(item(text)) == clf.classify(item(text))


class TestTypeSafeClassifier:
    """The SDK is not installed here and the API is unreachable from this
    container, so these cover question construction and response parsing —
    the parts that are ours rather than the vendor's."""

    def test_parses_a_response_into_labels(self):
        result = _FakeResult(
            choices={
                "event_type": _FakeChoice("injury", 0.96),
                "availability": _FakeChoice("out_season", 0.93),
            },
            scores={"role": _FakeScore(3.0, 0.91)},
            nouls={"is_confirmed": _FakeNoul(0.97)},
        )
        c = TypeSafeClassifier._parse(result)
        assert c.event_type == "injury"
        assert c.availability == "out_season"
        assert c.role == "franchise"
        assert c.is_confirmed == pytest.approx(0.97)

    def test_rounds_a_fractional_score_to_a_label(self):
        """Score returns a probability-weighted float; we want a label, and the
        float must not survive as a magnitude."""
        result = _FakeResult(
            choices={"event_type": _FakeChoice("injury", 0.9),
                     "availability": _FakeChoice("out_short", 0.9)},
            scores={"role": _FakeScore(2.4, 0.8)},
            nouls={"is_confirmed": _FakeNoul(0.9)},
        )
        assert TypeSafeClassifier._parse(result).role == "starter"

    def test_clamps_an_out_of_range_score(self):
        result = _FakeResult(
            choices={"event_type": _FakeChoice("injury", 0.9),
                     "availability": _FakeChoice("out_short", 0.9)},
            scores={"role": _FakeScore(99.0, 0.8)},
            nouls={"is_confirmed": _FakeNoul(0.9)},
        )
        assert TypeSafeClassifier._parse(result).role == ROLES[-1]

    def test_missing_api_key_fails_clearly(self, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        clf = TypeSafeClassifier()
        with pytest.raises((RuntimeError, ImportError)) as exc:
            clf.classify(item("x"))
        assert "TYPESAFE_API_KEY" in str(exc.value) or "typesafe-sdk" in str(exc.value)


# ─────────────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────────────


def _fixed(c: Classification):
    class _Fixed:
        def classify(self, item):
            return c
    return _Fixed()


class _FakeChoice:
    def __init__(self, choice, confidence):
        self.choice = choice
        self.confidence = confidence


class _FakeScore:
    def __init__(self, score, confidence):
        self.score = score
        self.confidence = confidence


class _FakeNoul:
    def __init__(self, noul):
        self.noul = noul


class _FakeResult:
    def __init__(self, choices, scores, nouls):
        self.choices = choices
        self.scores = scores
        self.nouls = nouls
