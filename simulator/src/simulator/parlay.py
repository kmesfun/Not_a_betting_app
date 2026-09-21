"""Risk-tiered parlay builder (PRD P0.8).

Two things this module takes seriously:

1. CORRELATION. Legs from the same game or the same team are not independent,
   so multiplying their probabilities is simply wrong — not a simplification,
   a bug. Every leg carries correlation keys, and v1 refuses to combine legs
   that share one. Exclusion is the conservative choice: it cannot produce a
   wrong number, where modelling correlation badly can. (PRD Section 10.)

2. ERROR PROPAGATION. Relative errors compound across legs. A five-leg long
   shot built from 1,000-sim legs carries ~18% relative error — "1 in 19,290"
   might really be 1 in 16,322. Every parlay reports its own uncertainty, and
   tiers refuse to publish a combination whose error is too wide to defend.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Leg:
    """One outcome eligible to appear in a parlay."""

    id: str
    description: str
    probability: float
    standard_error: float
    # Anything that makes two legs move together: a game id, a team id.
    # Legs sharing any key are never combined.
    correlation_keys: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not 0.0 < self.probability < 1.0:
            raise ValueError(f"leg {self.id}: probability must be in (0,1)")
        if self.standard_error < 0:
            raise ValueError(f"leg {self.id}: standard error cannot be negative")

    def conflicts_with(self, other: "Leg") -> bool:
        return bool(self.correlation_keys & other.correlation_keys)


@dataclass(frozen=True)
class Tier:
    name: str
    min_probability: float
    max_probability: float
    min_legs: int
    max_legs: int
    # Refuse to publish a parlay whose relative error exceeds this.
    max_relative_error: float = 0.05


DEFAULT_TIERS: tuple[Tier, ...] = (
    Tier("Safe", 0.60, 1.00, 2, 3),
    Tier("Balanced", 0.25, 0.60, 3, 4),
    Tier("Long shot", 0.0, 0.25, 4, 6, max_relative_error=0.08),
)


@dataclass(frozen=True)
class Parlay:
    tier: str
    legs: tuple[Leg, ...]

    @property
    def probability(self) -> float:
        return float(math.prod(leg.probability for leg in self.legs))

    @property
    def relative_error(self) -> float:
        """Relative errors of independent legs add in quadrature."""
        rel = [
            leg.standard_error / leg.probability
            for leg in self.legs
            if leg.probability > 0
        ]
        return float(math.sqrt(sum(r * r for r in rel)))

    @property
    def absolute_error(self) -> float:
        return self.probability * self.relative_error

    @property
    def odds_range(self) -> tuple[float, float]:
        """Honest '1 in N' bounds given the Monte Carlo error."""
        p, err = self.probability, self.absolute_error
        hi_p, lo_p = p + err, max(p - err, 1e-12)
        return (1.0 / hi_p, 1.0 / lo_p)

    def is_internally_consistent(self) -> bool:
        """No two legs share a correlation key."""
        return all(
            not a.conflicts_with(b) for a, b in itertools.combinations(self.legs, 2)
        )

    def describe(self) -> str:
        lines = [f"[{self.tier}] {self.probability:.2%}{self._odds_suffix()}"]
        for leg in self.legs:
            lines.append(f"   • {leg.description} — {leg.probability:.1%}")
        return "\n".join(lines)

    def _odds_suffix(self) -> str:
        """'1 in N' only where it tells the reader something.

        Above ~20% it doesn't: "1 in 1–1" for a 73% parlay is noise. The range
        is shown once it is wide enough to matter, and collapses to a single
        figure when the bounds round to the same number.
        """
        if self.probability > 0.20:
            return ""
        lo, hi = self.odds_range
        if round(lo) == round(hi):
            return f"  (1 in {lo:,.0f})"
        return f"  (1 in {lo:,.0f}–{hi:,.0f})"


def _combination_is_valid(combo: tuple[Leg, ...]) -> bool:
    return all(not a.conflicts_with(b) for a, b in itertools.combinations(combo, 2))


def build_parlays(
    legs: list[Leg],
    tiers: tuple[Tier, ...] = DEFAULT_TIERS,
    per_tier: int = 1,
    max_candidates: int = 50_000,
) -> list[Parlay]:
    """Build the best available parlay for each tier.

    "Best" means closest to the centre of the tier's probability band, which
    produces tiers that are genuinely distinct rather than all clustering at
    one edge — the tuning concern flagged in PRD Section 10.

    Correlated combinations are discarded before scoring, so a returned parlay
    is always safe to multiply.
    """
    results: list[Parlay] = []

    for tier in tiers:
        candidates: list[tuple[float, Parlay]] = []
        target = (tier.min_probability + tier.max_probability) / 2.0
        examined = 0

        for size in range(tier.min_legs, tier.max_legs + 1):
            for combo in itertools.combinations(legs, size):
                examined += 1
                if examined > max_candidates:
                    break
                if not _combination_is_valid(combo):
                    continue

                parlay = Parlay(tier=tier.name, legs=combo)
                p = parlay.probability
                if not (tier.min_probability <= p < tier.max_probability):
                    continue
                if parlay.relative_error > tier.max_relative_error:
                    continue

                candidates.append((abs(p - target), parlay))
            if examined > max_candidates:
                break

        candidates.sort(key=lambda pair: pair[0])
        results.extend(parlay for _, parlay in candidates[:per_tier])

    return results


def explain_precision_requirement(legs: list[Leg]) -> str:
    """Why the sim count matters here — useful for docs and for the UI."""
    if not legs:
        return "no legs"
    parlay = Parlay(tier="illustrative", legs=tuple(legs))
    lo, hi = parlay.odds_range
    return (
        f"{len(legs)} legs → {parlay.probability:.4%} "
        f"(±{parlay.relative_error:.1%} relative). "
        f"Published as '1 in {1/parlay.probability:,.0f}', "
        f"truly 1 in {lo:,.0f}–{hi:,.0f}."
    )
