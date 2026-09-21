"""Polymarket Gamma API client.

Gamma is fully public: no authentication, no API key, ~4,000 requests per
10 seconds. Only read endpoints are used here — the product never trades
(PRD Section 3), so the geo-restrictions that apply to order placement are
irrelevant.

Documented quirk, and the thing that breaks most first integrations:
`outcomePrices` comes back as a JSON-ENCODED STRING, not an array. It must be
parsed before indexing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from .base import MarketClient, MarketQuote

GAMMA_BASE = "https://gamma-api.polymarket.com"


class PolymarketClient(MarketClient):
    venue = "polymarket"

    def __init__(self, base_url: str = GAMMA_BASE, timeout: float = 10.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PolymarketClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def search_markets(self, query: str, limit: int = 20) -> list[dict]:
        resp = self._client.get(
            "/markets", params={"search": query, "limit": limit, "closed": "false"}
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_market(self, market_id: str) -> list[MarketQuote]:
        resp = self._client.get(f"/markets/{market_id}")
        resp.raise_for_status()
        return self._parse_market(resp.json())

    def _parse_market(self, payload: dict) -> list[MarketQuote]:
        outcomes = _maybe_json(payload.get("outcomes", []))
        prices = _maybe_json(payload.get("outcomePrices", []))

        if len(outcomes) != len(prices):
            raise ValueError(
                f"market {payload.get('id')}: {len(outcomes)} outcomes but "
                f"{len(prices)} prices"
            )

        as_of = datetime.now(timezone.utc)
        volume = _as_float(payload.get("volume"))
        return [
            MarketQuote(
                venue=self.venue,
                market_id=str(payload.get("id")),
                outcome=str(outcome),
                price=float(price),
                as_of=as_of,
                volume=volume,
            )
            for outcome, price in zip(outcomes, prices)
        ]


def _maybe_json(value):
    """Gamma returns some list fields as JSON-encoded strings. Handle both."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
