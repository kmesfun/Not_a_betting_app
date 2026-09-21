"""Shared types for prediction-market clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MarketQuote:
    """One outcome's current price on one venue."""

    venue: str
    market_id: str
    outcome: str
    price: float          # raw, pre-devig, on a 0-1 scale
    as_of: datetime
    volume: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.price <= 1.0:
            raise ValueError(f"price must be on a 0-1 scale, got {self.price}")


class MarketClient(ABC):
    """Interface every venue client implements.

    Clients return RAW prices. Devigging happens in normalize.devig, because it
    has to be applied across a complete set of mutually exclusive outcomes —
    which the client can't guarantee it has fetched.
    """

    venue: str

    @abstractmethod
    def fetch_market(self, market_id: str) -> list[MarketQuote]:
        """All outcome quotes for one market."""

    @abstractmethod
    def search_markets(self, query: str) -> list[dict]:
        """Find markets by text, for mapping league outcomes to venue ids."""
