"""Kalshi API client.

Public market data is readable without full trading authentication. Rate limits
are tiered; the entry Basic tier allows 200 read tokens/second and most requests
cost 10 tokens, so roughly 20 requests/second. A daily-refresh product needs a
few hundred requests per day, so the limit is not a constraint.

Kalshi quotes in CENTS (1-99). A 'yes' bid of 34 means 34%.

Note: a series of Kalshi markets ("which team wins the title") is a set of
separate binary contracts rather than one multi-outcome market, so they must be
collected and devigged together — see normalize.devig.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import MarketClient, MarketQuote
from .normalize import cents_to_probability

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiClient(MarketClient):
    venue = "kalshi"

    def __init__(
        self,
        base_url: str = KALSHI_BASE,
        timeout: float = 10.0,
        api_key: str | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=base_url, timeout=timeout, headers=headers)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "KalshiClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def search_markets(self, query: str, limit: int = 100) -> list[dict]:
        resp = self._client.get(
            "/markets", params={"series_ticker": query, "limit": limit, "status": "open"}
        )
        resp.raise_for_status()
        return resp.json().get("markets", [])

    def fetch_market(self, market_id: str) -> list[MarketQuote]:
        """One binary contract. `market_id` is a Kalshi ticker."""
        resp = self._client.get(f"/markets/{market_id}")
        resp.raise_for_status()
        return [self._parse_market(resp.json()["market"])]

    def fetch_series(self, series_ticker: str) -> list[MarketQuote]:
        """Every contract in a series — e.g. all teams in a title market."""
        return [self._parse_market(m) for m in self.search_markets(series_ticker)]

    def _parse_market(self, market: dict) -> MarketQuote:
        # Prefer the midpoint of the bid/ask; fall back to last trade.
        bid = market.get("yes_bid")
        ask = market.get("yes_ask")
        if bid is not None and ask is not None and (bid or ask):
            cents = (float(bid) + float(ask)) / 2.0
        else:
            cents = float(market.get("last_price") or 0.0)

        return MarketQuote(
            venue=self.venue,
            market_id=str(market.get("ticker")),
            outcome=str(market.get("yes_sub_title") or market.get("title") or market.get("ticker")),
            price=cents_to_probability(cents),
            as_of=datetime.now(timezone.utc),
            volume=_as_float(market.get("volume")),
        )


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
