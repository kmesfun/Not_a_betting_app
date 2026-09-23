import pytest

from simulator.markets import DevigMethod, cents_to_probability, devig, implied_odds
from simulator.markets.base import MarketQuote
from simulator.markets.polymarket import PolymarketClient


class TestCentsConversion:
    def test_converts_kalshi_cents(self):
        assert cents_to_probability(34) == pytest.approx(0.34)

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            cents_to_probability(140)


class TestDevig:
    def test_removes_overround(self):
        # These sum to 1.15 — a 15% overround.
        raw = {"A": 0.50, "B": 0.40, "C": 0.25}
        result = devig(raw)
        assert result.overround == pytest.approx(0.15)
        assert sum(result.probabilities) == pytest.approx(1.0)

    def test_preserves_ordering(self):
        raw = {"A": 0.50, "B": 0.40, "C": 0.25}
        p = devig(raw).as_dict()
        assert p["A"] > p["B"] > p["C"]

    def test_fair_market_is_unchanged(self):
        raw = {"A": 0.6, "B": 0.4}
        result = devig(raw)
        assert result.overround == pytest.approx(0.0)
        assert result.probabilities == pytest.approx([0.6, 0.4])

    @pytest.mark.parametrize("method", list(DevigMethod))
    def test_all_methods_normalize(self, method):
        raw = {"A": 0.52, "B": 0.30, "C": 0.20, "D": 0.08}
        result = devig(raw, method=method)
        assert sum(result.probabilities) == pytest.approx(1.0)
        assert all(v > 0 for v in result.probabilities)

    def test_power_method_shrinks_longshots_more(self):
        # Favourite-longshot bias: the power method should take proportionally
        # more away from the longshot than the proportional method does.
        raw = {"fav": 0.80, "longshot": 0.35}
        prop = devig(raw, method=DevigMethod.MULTIPLICATIVE).as_dict()
        power = devig(raw, method=DevigMethod.POWER).as_dict()
        assert power["longshot"] < prop["longshot"]
        assert power["fav"] > prop["fav"]

    def test_rejects_negative_prices(self):
        with pytest.raises(ValueError, match="negative"):
            devig({"A": -0.1, "B": 0.9})

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="no prices"):
            devig({})

    def test_additive_handles_thin_longshot(self):
        raw = {"A": 0.90, "B": 0.20, "C": 0.02}
        result = devig(raw, method=DevigMethod.ADDITIVE)
        assert all(v > 0 for v in result.probabilities)
        assert sum(result.probabilities) == pytest.approx(1.0)


class TestImpliedOdds:
    def test_formats_longshot(self):
        assert implied_odds(0.0005) == "1 in 2,000"

    def test_handles_zero(self):
        assert "no chance" in implied_odds(0.0)


class TestMarketQuote:
    def test_rejects_price_outside_unit_interval(self):
        from datetime import datetime, timezone
        with pytest.raises(ValueError, match="0-1 scale"):
            MarketQuote(
                venue="test", market_id="m", outcome="A",
                price=45.0, as_of=datetime.now(timezone.utc),
            )


class TestPolymarketParsing:
    """The JSON-encoded-string quirk is the thing that breaks integrations."""

    def test_parses_string_encoded_price_arrays(self):
        client = PolymarketClient.__new__(PolymarketClient)
        payload = {
            "id": "12345",
            "outcomes": '["Celtics", "Thunder", "Nuggets"]',
            "outcomePrices": '["0.31", "0.42", "0.27"]',
            "volume": "180000",
        }
        quotes = client._parse_market(payload)
        assert len(quotes) == 3
        assert {q.outcome for q in quotes} == {"Celtics", "Thunder", "Nuggets"}
        assert quotes[1].price == pytest.approx(0.42)
        assert quotes[0].volume == pytest.approx(180000.0)

    def test_parses_native_arrays_too(self):
        client = PolymarketClient.__new__(PolymarketClient)
        payload = {"id": "9", "outcomes": ["Yes", "No"], "outcomePrices": [0.6, 0.4]}
        quotes = client._parse_market(payload)
        assert len(quotes) == 2

    def test_rejects_mismatched_outcome_and_price_counts(self):
        client = PolymarketClient.__new__(PolymarketClient)
        payload = {"id": "7", "outcomes": '["A","B"]', "outcomePrices": '["0.5"]'}
        with pytest.raises(ValueError, match="2 outcomes but 1 prices"):
            client._parse_market(payload)


class TestIncompleteBook:
    """A book summing below 1 means outcomes are missing, not a negative vig.

    Found while wiring the dashboard: the mock market priced only the top 8
    teams, so prices summed to ~0.91 and devig normalized them all UP to
    absorb the other 22 teams' share — inflating every price. That is the
    systematic bias devigging exists to prevent.
    """

    def test_partial_book_is_rejected(self):
        from simulator.markets.normalize import IncompleteBookError
        # Top 3 of a 30-team field: legitimately sums well below 1.
        with pytest.raises(IncompleteBookError, match="partial book"):
            devig({"OKC": 0.44, "DAL": 0.09, "DEN": 0.09})

    def test_error_names_the_shortfall_and_the_fix(self):
        from simulator.markets.normalize import IncompleteBookError
        try:
            devig({"A": 0.30, "B": 0.20})
        except IncompleteBookError as exc:
            msg = str(exc)
            assert "0.5000" in msg
            assert "complete set" in msg
        else:
            pytest.fail("expected IncompleteBookError")

    def test_complete_book_with_overround_still_works(self):
        full = {f"T{i}": 0.03 for i in range(30)}
        full["OKC"] = 0.25
        result = devig(full)
        assert result.overround > 0
        assert sum(result.probabilities) == pytest.approx(1.0)

    def test_slightly_under_one_is_tolerated(self):
        # Wide spreads on a thin but complete book can dip just under 1.
        result = devig({"A": 0.60, "B": 0.39})
        assert sum(result.probabilities) == pytest.approx(1.0)

    def test_incomplete_book_error_is_a_value_error(self):
        from simulator.markets.normalize import IncompleteBookError
        assert issubclass(IncompleteBookError, ValueError)
