"""Model-vs-market divergence detection — the core product (PRD 9.9).

The thesis: championship odds barely move on a quiet day, so "here are the
odds" is a reference tool people check occasionally. "The market hasn't priced
last night's injury yet" is a reason to open something daily. This module
computes that signal and decides when it is worth interrupting someone for.

Two refinements over a naive percentage-point delta:

1. A gap is only meaningful relative to the model's OWN uncertainty. A 3-point
   gap where the model's standard error is 0.2pt is a real disagreement; the
   same gap where the SE is 1.5pt is mostly noise. We score in units of
   standard error, not raw points.

2. A divergence that has already been reported is not news. Re-alerting the
   same standing gap every morning is exactly how a digest trains people to
   ignore it. State is tracked so only new or materially changed gaps fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


from .markets.base import MarketQuote
from .markets.normalize import DevigMethod, devig

# Below this, a standard error reflects sampling granularity rather than real
# confidence — a 50,000-sim run cannot resolve probability differences finer
# than about 1 in 50,000.
MIN_RESOLVABLE_SE = 1e-4

# Past roughly ten standard errors the exact figure stops being informative.
MAX_Z = 99.9


@dataclass(frozen=True)
class Divergence:
    """One outcome where the model and the market disagree."""

    outcome: str
    model_probability: float
    model_se: float
    market_probability: float
    venue_probabilities: dict[str, float]
    as_of: datetime

    @property
    def delta(self) -> float:
        """Model minus market. Positive = model thinks the market is too low."""
        return self.model_probability - self.market_probability

    @property
    def z_score(self) -> float:
        """Gap measured in standard errors of the model estimate.

        Two guards. When the model puts an outcome at (or near) zero, its
        binomial standard error collapses toward zero too, and an uncapped
        ratio produces absurd values like z = -8,119. The floor reflects the
        finest probability a finite sample can actually resolve, and the cap
        keeps the number readable — past about 10 standard errors the
        distinction between "very confident" and "absurdly confident" carries
        no additional information for a reader.
        """
        se = max(self.model_se, MIN_RESOLVABLE_SE)
        return float(max(-MAX_Z, min(MAX_Z, self.delta / se)))

    @property
    def direction(self) -> str:
        return "undervalued" if self.delta > 0 else "overvalued"

    @property
    def delta_points(self) -> float:
        """The gap in percentage points, which is how it gets displayed."""
        return self.delta * 100.0

    def describe(self) -> str:
        venues = ", ".join(
            f"{v.title()} {p:.1%}" for v, p in sorted(self.venue_probabilities.items())
        )
        return (
            f"{self.outcome}: model {self.model_probability:.1%} "
            f"(±{self.model_se:.2%}) vs {venues} "
            f"→ {self.direction} by {abs(self.delta_points):.1f}pts"
        )


@dataclass
class AlertRule:
    """When a divergence is worth sending."""

    min_absolute_delta: float = 0.03   # 3 percentage points
    min_z_score: float = 2.0           # and at least 2 model standard errors
    min_market_probability: float = 0.005
    # A previously-alerted gap must change by this much to re-fire.
    rearm_delta: float = 0.02

    def qualifies(self, d: Divergence) -> bool:
        return (
            abs(d.delta) >= self.min_absolute_delta
            and abs(d.z_score) >= self.min_z_score
            and d.market_probability >= self.min_market_probability
        )


def detect(
    model_probabilities: dict[str, float],
    model_standard_errors: dict[str, float],
    quotes: list[MarketQuote],
    devig_method: DevigMethod = DevigMethod.POWER,
) -> list[Divergence]:
    """Compare model output against market quotes, devigging per venue.

    Quotes are grouped by venue and devigged within the venue, because the
    overround belongs to the venue's own book. Cross-venue averaging happens
    only after each venue is independently normalized.
    """
    if not quotes:
        return []

    by_venue: dict[str, dict[str, float]] = {}
    for q in quotes:
        by_venue.setdefault(q.venue, {})[q.outcome] = q.price

    normalized: dict[str, dict[str, float]] = {}
    for venue, raw in by_venue.items():
        if len(raw) < 2:
            # A lone contract has no complementary set to devig against; use it
            # raw rather than dropping the venue entirely.
            normalized[venue] = dict(raw)
        else:
            normalized[venue] = devig(raw, method=devig_method).as_dict()

    as_of = datetime.now(timezone.utc)
    divergences: list[Divergence] = []

    for outcome, model_p in model_probabilities.items():
        venue_probs = {
            venue: probs[outcome] for venue, probs in normalized.items() if outcome in probs
        }
        if not venue_probs:
            continue

        values = list(venue_probs.values())
        consensus = float(sum(values) / len(values))
        divergences.append(
            Divergence(
                outcome=outcome,
                model_probability=model_p,
                model_se=model_standard_errors.get(outcome, 0.0),
                market_probability=consensus,
                venue_probabilities=venue_probs,
                as_of=as_of,
            )
        )

    return sorted(divergences, key=lambda d: abs(d.delta), reverse=True)


@dataclass
class DigestState:
    """What has already been reported, so standing gaps don't re-fire."""

    last_alerted: dict[str, float] = field(default_factory=dict)

    def is_news(self, d: Divergence, rule: AlertRule) -> bool:
        previous = self.last_alerted.get(d.outcome)
        if previous is None:
            return True
        return abs(d.delta - previous) >= rule.rearm_delta

    def record(self, d: Divergence) -> None:
        self.last_alerted[d.outcome] = d.delta


def build_digest(
    divergences: list[Divergence],
    rule: AlertRule,
    state: DigestState,
    max_items: int = 5,
) -> list[Divergence]:
    """Select what to send. An empty list means send nothing.

    Sending nothing is a correct and important outcome (PRD P0.9): a digest
    that fires every day regardless of whether anything happened is a digest
    people stop opening.
    """
    selected: list[Divergence] = []
    for d in divergences:
        if len(selected) >= max_items:
            break
        if rule.qualifies(d) and state.is_news(d, rule):
            selected.append(d)
            state.record(d)
    return selected


def render_digest(items: list[Divergence]) -> str:
    """Plain-text digest body."""
    if not items:
        return ""
    lines = ["Model vs market — today's gaps", ""]
    for d in items:
        lines.append(f"• {d.describe()}")
    lines.append("")
    lines.append(
        "Probabilities from our simulation, market prices devigged. "
        "Analysis only — not betting advice."
    )
    return "\n".join(lines)
