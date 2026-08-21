import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from simulator.api import app  # noqa: E402

client = TestClient(app)


def test_dashboard_serves_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Live Season Simulator" in res.text


def test_health():
    assert client.get("/v1/health").json() == {"status": "ok"}


def test_update_full_league():
    res = client.get("/v1/update", params={"sims": 100})
    assert res.status_code == 200
    body = res.json()
    assert body["league"] == "NBA"
    assert len(body["teams"]) == 30


def test_update_scoped_team_case_insensitive():
    res = client.get("/v1/update", params={"team": "bos", "sims": 100})
    assert res.status_code == 200
    assert res.json()["team"]["team"] == "BOS"


def test_update_unknown_team_is_404():
    res = client.get("/v1/update", params={"team": "ZZZ", "sims": 100})
    assert res.status_code == 404


def test_update_unknown_league_is_404():
    res = client.get("/v1/update", params={"league": "mlb"})
    assert res.status_code == 404


def test_explain_injury_reduces_odds_for_a_favorite():
    res = client.get(
        "/v1/explain-injury",
        params={"team": "OKC", "value": 200, "ramp_games": 0, "sims": 500},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["team"] == "OKC"
    assert body["delta"] < 0


def test_explain_injury_unknown_team_is_404():
    res = client.get("/v1/explain-injury", params={"team": "ZZZ", "value": 100, "sims": 100})
    assert res.status_code == 404


def test_explain_trade_moves_both_sides_opposite_directions():
    res = client.get(
        "/v1/explain-trade",
        params={"team_in": "bos", "team_out": "mia", "value": 150, "ramp_games": 0, "sims": 500},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["team_in"]["team"] == "BOS"
    assert body["team_out"]["team"] == "MIA"
    in_delta = body["team_in"]["championship_probability_after"] - body["team_in"]["championship_probability_before"]
    out_delta = body["team_out"]["championship_probability_after"] - body["team_out"]["championship_probability_before"]
    assert in_delta > 0
    assert out_delta <= 0


def test_explain_trade_same_team_is_400():
    res = client.get(
        "/v1/explain-trade",
        params={"team_in": "BOS", "team_out": "BOS", "value": 100, "sims": 100},
    )
    assert res.status_code == 400
