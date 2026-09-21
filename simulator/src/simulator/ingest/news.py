"""Turn unstructured injury/transaction news into structured RosterEvents.

This exists because structured trade data is the weakest feed available at any
price. Injury reports are well covered; "the Suns traded X for Y" arrives as
prose. This is the one place in the system where semantic understanding is
genuinely needed, and it uses TypeSafe's System One model (Jev) to supply it.

────────────────────────────────────────────────────────────────────────────
THE BOUNDARY — read this before changing anything in this file
────────────────────────────────────────────────────────────────────────────

The model classifies. Code assigns numbers. Never the other way round.

The model answers "is this player a franchise player?" and "how long are they
out?" and returns LABELS. Code then looks the label pair up in ELO_DELTA_TABLE
to get the magnitude. No float that came out of a model ever becomes a
`value_delta`.

This is not fussiness. The product's asset is a calibrated, reproducible
probability that gets scored against prediction markets. If a model-derived
magnitude enters the simulation:

  - Odds stop being reproducible. Re-running last month's inputs against a
    newer model version yields different history.
  - Backtesting becomes dishonest. You cannot replay last season against a
    model that did not exist then and call the result a track record.
  - The divergence claim collapses. "The market is mispriced" degrades into
    "the market disagrees with a language model's guess."

ELO_DELTA_TABLE is meant to be FITTED against historical market moves and
version-controlled. That is what makes a magnitude defensible. A model's
opinion about how many Elo points a player is worth is not.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from ..ratings import RosterEvent

# ─────────────────────────────────────────────────────────────────────────────
# Label vocabularies. Closed sets: the model must answer inside them.
# ─────────────────────────────────────────────────────────────────────────────

EVENT_TYPES: dict[str, str] = {
    "injury": "A player is hurt, ill, or newly listed as unavailable.",
    "trade": "A player moved between teams in an exchange.",
    "signing": "A team added a player who was not previously on its roster.",
    "return": "A previously unavailable player is coming back to play.",
    "suspension": "A player is barred from playing for disciplinary reasons.",
    "unrelated": "The report is not about a change to a team's available roster.",
}

AVAILABILITY: dict[str, str] = {
    "out_season": "Will not play again this season.",
    "out_multiweek": "Expected to miss more than two weeks but return this season.",
    "out_short": "Expected to miss between one game and two weeks.",
    "questionable": "May or may not play the next game; status genuinely unsettled.",
    "available": "Expected to play as normal.",
}

# Ordered least to most important — Score primitives take ordered levels.
ROLES: list[str] = ["depth", "rotation", "starter", "franchise"]

ROLE_DESCRIPTIONS: list[str] = [
    "Depth: end of bench or reserve. Rarely plays meaningful minutes.",
    "Rotation: plays regularly but does not start. A contributor, not a fixture.",
    "Starter: a regular starter and a significant part of the team's output.",
    "Franchise: the team's best player. Losing this player materially changes "
    "how good the team is.",
]

# ─────────────────────────────────────────────────────────────────────────────
# CODE OWNS THE NUMBERS.
#
# Units are Elo points, matching ratings.RosterEvent.value_delta. Negative means
# the team got worse.
#
# These are PLACEHOLDERS calibrated by judgment, not data. The sanity anchor:
# roughly 10 Elo points ≈ one win over an 82-game season, so a franchise player
# lost for the year (~9-11 wins) lands near -110, which turns a 1600-rated
# contender into a 1490-rated middling playoff team. That is about the right
# magnitude, but "about right" is not good enough to publish odds on.
#
# FITTING THESE IS A WEEK 1 TASK. Take historical star injuries where the
# pre/post market move is known and solve for the values that reproduce it.
# Until then, every downstream number inherits this guess's error.
# ─────────────────────────────────────────────────────────────────────────────

ELO_DELTA_TABLE: dict[tuple[str, str], float] = {
    ("franchise", "out_season"): -110.0,
    ("franchise", "out_multiweek"): -45.0,
    ("franchise", "out_short"): -15.0,
    ("franchise", "questionable"): -7.0,
    ("franchise", "available"): 0.0,

    ("starter", "out_season"): -50.0,
    ("starter", "out_multiweek"): -20.0,
    ("starter", "out_short"): -7.0,
    ("starter", "questionable"): -3.0,
    ("starter", "available"): 0.0,

    ("rotation", "out_season"): -18.0,
    ("rotation", "out_multiweek"): -7.0,
    ("rotation", "out_short"): -3.0,
    ("rotation", "questionable"): -1.0,
    ("rotation", "available"): 0.0,

    ("depth", "out_season"): -4.0,
    ("depth", "out_multiweek"): -2.0,
    ("depth", "out_short"): -1.0,
    ("depth", "questionable"): 0.0,
    ("depth", "available"): 0.0,
}

# A return or signing gives value back: the mirror of an injury.
RETURNING_EVENTS = {"return", "signing"}

# Integration ramp, in GAMES (matching RosterEvent.ramp_games). An injury
# applies instantly — a player who is out is out. An arrival takes time.
RAMP_GAMES = {"injury": 0, "suspension": 0, "trade": 5, "signing": 7, "return": 3}


@dataclass(frozen=True)
class NewsItem:
    """One piece of unstructured reporting."""

    text: str
    published: date
    source: str
    url: str | None = None


@dataclass(frozen=True)
class Classification:
    """What the model returns: labels and confidences. Never magnitudes.

    Every float here is used ONLY for routing — deciding whether to trust the
    labels enough to act. None is ever arithmetic input to a rating change.
    """

    event_type: str
    availability: str
    role: str
    player_name: str | None = None
    team: str | None = None

    event_confidence: float = 0.0
    availability_confidence: float = 0.0
    role_confidence: float = 0.0
    # Noul: probability the report states a confirmed fact rather than a rumour.
    # Nouls carry no separate confidence — the probability IS the answer.
    is_confirmed: float = 0.0

    raw: dict = field(default_factory=dict, repr=False)

    @property
    def min_confidence(self) -> float:
        """The weakest link. A chain of judgments is as good as its worst."""
        return min(
            self.event_confidence,
            self.availability_confidence,
            self.role_confidence,
        )

    def is_roster_change(self) -> bool:
        return self.event_type != "unrelated"


@dataclass(frozen=True)
class ReviewPolicy:
    """Confidence gating.

    Applying a roster event moves published odds and can fire an alert telling
    someone the market is wrong. High-stakes, so it sits at the strict end of
    TypeSafe's guidance (>0.9 act automatically, 0.5-0.9 proceed with caution,
    <0.5 route to a human).

    Holding an event for review costs a few minutes of attention. Applying a
    wrong one costs credibility, and credibility is the product.
    """

    auto_apply_above: float = 0.90
    discard_below: float = 0.50
    # Hedged reporting ("could miss time") must not move anything.
    min_confirmation: float = 0.75


@dataclass(frozen=True)
class Extraction:
    """The outcome of processing one news item."""

    item: NewsItem
    classification: Classification | None
    event: RosterEvent | None
    status: str  # "applied" | "needs_review" | "discarded" | "unrelated"
    reason: str

    @property
    def applied(self) -> bool:
        return self.status == "applied"


def elo_delta(role: str, availability: str, event_type: str) -> float:
    """Look up the magnitude. A pure function of three labels.

    Raises on an unknown pair rather than defaulting to zero — a silent zero is
    an event that quietly does nothing, which is much harder to notice than an
    exception.
    """
    key = (role, availability)
    if key not in ELO_DELTA_TABLE:
        raise KeyError(
            f"no Elo entry for role={role!r}, availability={availability!r}. "
            f"Add it to ELO_DELTA_TABLE rather than defaulting."
        )
    magnitude = ELO_DELTA_TABLE[key]
    if event_type in RETURNING_EVENTS:
        return -magnitude
    return magnitude


def to_roster_event(classification: Classification, team: str) -> RosterEvent:
    """Build a RosterEvent from labels alone.

    Deterministic: identical labels always produce an identical event,
    regardless of how confident the model happened to be. Confidence decides
    *whether* to call this, never what it returns.
    """
    return RosterEvent(
        team=team,
        value_delta=elo_delta(
            classification.role, classification.availability, classification.event_type
        ),
        ramp_games=RAMP_GAMES.get(classification.event_type, 0),
        label=(
            f"{classification.player_name or 'player'}: "
            f"{classification.event_type} ({classification.availability})"
        ),
    )


@runtime_checkable
class Classifier(Protocol):
    """Anything that can turn a NewsItem into labels."""

    def classify(self, item: NewsItem) -> Classification: ...


class TypeSafeClassifier:
    """Classifier backed by TypeSafe's System One model (Jev).

    All questions go in ONE request. They are independent judgments over the
    same state, so they run in parallel and cannot see one another's answers —
    batching is both cheaper and the documented pattern.

    Requires TYPESAFE_API_KEY in the environment.
    """

    def __init__(self, client=None) -> None:
        self._client = client

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from typesafe_sdk import TypeSafeClient
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "TypeSafeClassifier needs the SDK: pip install typesafe-sdk. "
                "For offline work use KeywordClassifier instead."
            ) from exc
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise RuntimeError(
                "TYPESAFE_API_KEY is not set. Export it, or use KeywordClassifier."
            )
        self._client = TypeSafeClient()
        return self._client

    @staticmethod
    def build_questions() -> dict:
        """The question set, separated so it can be inspected and tested."""
        from typesafe_sdk import Choice, Noul, Score

        return {
            "event_type": Choice(
                instructions=(
                    "What kind of roster change does this report describe? "
                    "Choose 'unrelated' if it does not change which players are "
                    "available to a team."
                ),
                criteria=dict(EVENT_TYPES),
            ),
            "availability": Choice(
                instructions=(
                    "How long will the player named in this report be "
                    "unavailable? If the report describes a player becoming "
                    "available again, answer 'available'."
                ),
                criteria=dict(AVAILABILITY),
            ),
            "role": Score(
                instructions=(
                    "How important is this player to their team's on-court results?"
                ),
                criteria=list(ROLE_DESCRIPTIONS),
            ),
            "is_confirmed": Noul(
                instructions=(
                    "Does this report state the change as confirmed fact, rather "
                    "than as a rumour, a possibility, or something under evaluation?"
                ),
            ),
        }

    def classify(self, item: NewsItem) -> Classification:
        client = self._ensure_client()
        state = {
            "report": item.text,
            "published": item.published.isoformat(),
            "source": item.source,
        }
        return self._parse(client.system_one(state, self.build_questions()))

    @staticmethod
    def _parse(result) -> Classification:
        """Map an SDK response onto a Classification.

        Score returns a probability-weighted float across ordered levels, so it
        is rounded to the nearest level to recover a label. The float itself is
        deliberately discarded — a "role of 2.7" is not a magnitude, and letting
        it become one would breach the boundary this module exists to hold.
        """
        event = result.choices["event_type"]
        availability = result.choices["availability"]
        role = result.scores["role"]
        confirmed = result.nouls["is_confirmed"]

        index = max(0, min(len(ROLES) - 1, int(round(role.score))))

        return Classification(
            event_type=event.choice,
            availability=availability.choice,
            role=ROLES[index],
            event_confidence=float(event.confidence),
            availability_confidence=float(availability.confidence),
            role_confidence=float(role.confidence),
            is_confirmed=float(confirmed.noul),
        )


class KeywordClassifier:
    """Deterministic offline classifier.

    Not a good extractor — it exists so the pipeline runs, and tests pass,
    without a network call or an API key. Also useful as a control: if this does
    nearly as well as the model on your sample, the model is not paying for
    itself.
    """

    SEASON_ENDING = ("out for the season", "season-ending", "torn acl", "ruptured")
    MULTIWEEK = ("expected to miss", "weeks", "placed on injured reserve")
    SHORT = ("day-to-day", "questionable", "game-time decision")
    RETURNS = ("returns", "activated", "cleared to play", "will play")
    TRADES = ("traded", "acquired", "in exchange for", "deal sending")

    def classify(self, item: NewsItem) -> Classification:
        text = item.text.lower()

        if any(k in text for k in self.TRADES):
            event_type = "trade"
        elif any(k in text for k in self.RETURNS):
            event_type = "return"
        elif any(k in text for k in self.SEASON_ENDING + self.MULTIWEEK + self.SHORT):
            event_type = "injury"
        else:
            event_type = "unrelated"

        if event_type == "return":
            availability = "available"
        elif any(k in text for k in self.SEASON_ENDING):
            availability = "out_season"
        elif any(k in text for k in self.MULTIWEEK):
            availability = "out_multiweek"
        elif "day-to-day" in text:
            availability = "out_short"
        elif "questionable" in text or "game-time" in text:
            availability = "questionable"
        else:
            availability = "available"

        if "star" in text or "mvp" in text or "all-star" in text:
            role = "franchise"
        elif "starting" in text or "starter" in text:
            role = "starter"
        else:
            role = "rotation"

        hedged = any(w in text for w in
                     ("could", "may ", "reportedly", "believed", "rumou"))

        return Classification(
            event_type=event_type,
            availability=availability,
            role=role,
            # Deliberately mid-range: a keyword match is not a confident
            # judgment, so under the default policy these land in review rather
            # than silently moving published odds.
            event_confidence=0.6,
            availability_confidence=0.6,
            role_confidence=0.6,
            is_confirmed=0.4 if hedged else 0.8,
        )


def extract(
    item: NewsItem,
    classifier: Classifier,
    team: str | None,
    policy: ReviewPolicy | None = None,
) -> Extraction:
    """Classify one report and, if it clears the gate, build a RosterEvent.

    Four outcomes, three of which produce no event:
      unrelated    — not a roster change
      discarded    — the model could not read it
      needs_review — plausible but not trustworthy enough to move odds
      applied      — confident, confirmed, ready to simulate
    """
    policy = policy or ReviewPolicy()
    classification = classifier.classify(item)

    if not classification.is_roster_change():
        return Extraction(item, classification, None, "unrelated",
                          "not a roster change")

    if classification.min_confidence < policy.discard_below:
        return Extraction(
            item, classification, None, "discarded",
            f"confidence {classification.min_confidence:.2f} below "
            f"{policy.discard_below:.2f}",
        )

    if classification.is_confirmed < policy.min_confirmation:
        return Extraction(
            item, classification, None, "needs_review",
            f"report reads as unconfirmed ({classification.is_confirmed:.2f})",
        )

    if classification.min_confidence < policy.auto_apply_above:
        return Extraction(
            item, classification, None, "needs_review",
            f"confidence {classification.min_confidence:.2f} below auto-apply "
            f"threshold {policy.auto_apply_above:.2f}",
        )

    resolved = team or classification.team
    if resolved is None:
        return Extraction(
            item, classification, None, "needs_review",
            "could not map the report to a team in the league",
        )

    return Extraction(item, classification, to_roster_event(classification, resolved),
                      "applied", "confident and confirmed")
