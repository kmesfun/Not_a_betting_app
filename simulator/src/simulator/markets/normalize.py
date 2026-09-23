"""Turn raw market prices into probabilities comparable with model output.

This is the step most naive model-vs-market comparisons get wrong. Contract
prices across a set of mutually exclusive outcomes sum to MORE than 1 — the
excess is the overround (vig). Model probabilities sum to exactly 1. Comparing
them directly makes the market look systematically more confident than it is on
every single outcome, which would make the whole product read as "the market is
always too high" — a bias, not a signal.

So raw prices must be devigged before any delta is computed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import math


# How far below 1.0 a book may sum before we treat it as incomplete rather
# than as a (nonsensical) negative overround. Wide spreads on thin markets can
# pull a complete book slightly under; a missing chunk of the field pulls it
# well under.
INCOMPLETE_BOOK_TOLERANCE = 0.02


class IncompleteBookError(ValueError):
    """Raised when prices sum below 1, which means outcomes are missing.

    Separate from a plain ValueError so callers can distinguish "this feed is
    incomplete, go fetch the rest" from "these prices are malformed".
    """


class DevigMethod(str, Enum):
    MULTIPLICATIVE = "multiplicative"  # proportional; the standard default
    ADDITIVE = "additive"              # spreads the overround evenly
    POWER = "power"                    # fits an exponent; better on longshots


@dataclass(frozen=True)
class NormalizedMarket:
    """A devigged market ready to compare against model probabilities."""

    outcomes: tuple[str, ...]
    probabilities: list[float]
    overround: float
    method: DevigMethod

    def as_dict(self) -> dict[str, float]:
        return {o: float(p) for o, p in zip(self.outcomes, self.probabilities)}


def cents_to_probability(cents: float) -> float:
    """Kalshi quotes contracts in cents (1-99), which read directly as %."""
    if not 0.0 <= cents <= 100.0:
        raise ValueError(f"contract price out of range: {cents}")
    return cents / 100.0


def _power_devig(raw: list[float], tol: float = 1e-10, max_iter: int = 100) -> list[float]:
    """Find k such that sum(raw ** k) == 1.

    The power method shrinks favourites less and longshots more than the
    proportional method, which better matches observed favourite-longshot bias.
    Worth using for championship markets specifically, where the tail is long
    and a proportional devig overstates longshot probabilities.
    """
    lo, hi = 0.01, 10.0
    k = 1.0
    for _ in range(max_iter):
        k = (lo + hi) / 2.0
        total = sum(v ** k for v in raw)
        if abs(total - 1.0) < tol:
            break
        if total > 1.0:
            lo = k
        else:
            hi = k
    return [v ** k for v in raw]


def devig(
    raw_prices: dict[str, float] | list[float],
    method: DevigMethod = DevigMethod.MULTIPLICATIVE,
    outcomes: tuple[str, ...] | None = None,
) -> NormalizedMarket:
    """Remove the overround from a set of mutually exclusive outcome prices."""
    if isinstance(raw_prices, dict):
        outcomes = tuple(raw_prices.keys())
        raw = [float(v) for v in raw_prices.values()]
    else:
        raw = [float(v) for v in raw_prices]
        if outcomes is None:
            outcomes = tuple(f"outcome_{i}" for i in range(len(raw)))

    if len(raw) == 0:
        raise ValueError("no prices given")
    if any(v < 0 for v in raw):
        raise ValueError("prices cannot be negative")

    total = float(sum(raw))
    if total <= 0:
        raise ValueError("prices sum to zero")

    if total < 1.0 - INCOMPLETE_BOOK_TOLERANCE:
        # A real book over a complete set of mutually exclusive outcomes sums
        # to MORE than 1 — the excess is the vig. Summing to less than 1 means
        # outcomes are missing (a top-N slice rather than the full field), and
        # normalizing that up to 1 silently inflates every price to absorb the
        # share belonging to outcomes that were never fetched. That is a
        # systematic bias dressed as a correction, and it is exactly what
        # devigging is supposed to prevent. Fetch the whole field instead.
        raise IncompleteBookError(
            f"prices sum to {total:.4f}, below 1 — this looks like a partial "
            f"book ({len(raw)} outcomes). Devigging it would inflate every "
            f"price. Fetch the complete set of mutually exclusive outcomes."
        )

    if method is DevigMethod.MULTIPLICATIVE:
        probs = [v / total for v in raw]
    elif method is DevigMethod.ADDITIVE:
        shift = (total - 1.0) / len(raw)
        # Additive devig can push thin longshots negative; floor and renormalize.
        probs = [max(v - shift, 1e-9) for v in raw]
        s = sum(probs)
        probs = [v / s for v in probs]
    elif method is DevigMethod.POWER:
        probs = _power_devig(raw)
        s = sum(probs)
        probs = [v / s for v in probs]
    else:
        raise ValueError(f"unknown devig method: {method}")

    return NormalizedMarket(
        outcomes=outcomes,
        probabilities=probs,
        overround=total - 1.0,
        method=method,
    )


def implied_odds(probability: float) -> str:
    """Human-readable '1 in N' for display next to a probability."""
    if probability <= 0:
        return "no chance priced"
    return f"1 in {1.0 / probability:,.0f}"
