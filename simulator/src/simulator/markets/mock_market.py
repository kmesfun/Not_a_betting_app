"""Synthetic prediction-market quotes, for demoing divergence without a feed.

The counterpart to mock_data.py: that module stands in for a real ratings
provider, this one stands in for live Polymarket/Kalshi prices. Both exist so
the pipeline can be built and shown end to end before the real feeds are wired
up, and both must be labelled as mock wherever their output is displayed.

Two scenarios, because the product has two behaviours worth seeing:

  quiet   - the market broadly agrees with the model. Small gaps, nothing
            worth interrupting anyone for. The digest should be EMPTY, and
            that is the correct outcome, not a failure.

  stale   - a roster event has moved the model but the market has not
            repriced yet. This is the product: the gap is the signal.

Prices carry a realistic overround so the devigging path is exercised. Without
it a demo silently skips the step that matters most in a real comparison.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from .base import MarketQuote

# Championship markets on real venues carry a few percent of overround.
DEFAULT_OVERROUND = 0.012

VENUE = "kalshi-mock"


def quotes_from_probabilities(
    probabilities: dict[str, float],
    overround: float = DEFAULT_OVERROUND,
    jitter: float = 0.0,
    seed: int | None = None,
) -> list[MarketQuote]:
    """Turn a set of probabilities into priced quotes.

    `jitter` adds per-outcome noise as a fraction of each probability, so a
    "quiet" market disagrees slightly and unevenly, the way a real book does,
    rather than matching the model exactly.
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    scale = 1.0 + overround

    quotes: list[MarketQuote] = []
    for outcome, p in probabilities.items():
        noisy = p * (1.0 + rng.uniform(-jitter, jitter)) if jitter else p
        price = min(0.99, max(0.001, noisy * scale))
        quotes.append(
            MarketQuote(
                venue=VENUE,
                market_id=f"MOCK-CHAMP-{outcome}",
                outcome=outcome,
                price=price,
                as_of=now,
            )
        )
    return quotes


def quiet_market(
    result,
    overround: float = DEFAULT_OVERROUND,
    seed: int | None = 2026,
) -> list[MarketQuote]:
    """A market that broadly agrees with the model.

    Prices the COMPLETE field, never a top-N slice. A partial book sums to
    less than 1 and devigging it inflates every price to absorb the missing
    outcomes' share — see IncompleteBookError in normalize.py. Slice for
    display after devigging, never before.

    Jitter is kept small enough that gaps stay under the default alert
    threshold, so this scenario demonstrates the digest correctly staying
    silent.
    """
    probs = {t.team: t.championship_probability for t in result.teams.values()}
    return quotes_from_probabilities(probs, overround=overround, jitter=0.06, seed=seed)


def stale_market(
    before_result,
    overround: float = DEFAULT_OVERROUND,
) -> list[MarketQuote]:
    """A market still quoting the pre-event board.

    Pass the simulation from BEFORE the roster event; the caller compares it
    against the post-event model. That is exactly the real situation the
    product is built to catch: the news has landed, our model has moved, and
    the market has not caught up.

    Prices the complete field, for the reason given in quiet_market.
    """
    probs = {t.team: t.championship_probability for t in before_result.teams.values()}
    return quotes_from_probabilities(probs, overround=overround)
