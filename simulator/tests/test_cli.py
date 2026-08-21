import json

import pytest

from simulator.cli import main


def test_update_unknown_league_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        main(["--league", "mlb", "update"])
    assert "Unknown league" in str(exc_info.value)


def test_update_unknown_team_exits_cleanly_not_a_crash():
    with pytest.raises(SystemExit) as exc_info:
        main(["--sims", "50", "update", "--team", "ZZZ"])
    assert "Unknown team" in str(exc_info.value)


def test_update_team_is_case_insensitive(capsys):
    main(["--sims", "50", "update", "--team", "bos"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["team"]["team"] == "BOS"


def test_explain_injury_unknown_team_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        main(["--sims", "50", "explain-injury", "--team", "ZZZ", "--value", "100"])
    assert "Unknown team" in str(exc_info.value)


def test_explain_trade_unknown_team_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        main(["--sims", "50", "explain-trade", "--team-in", "ZZZ", "--team-out", "BOS", "--value", "100"])
    assert "Unknown team" in str(exc_info.value)


def test_explain_trade_lowercase_teams_work(capsys):
    main(["--sims", "50", "explain-trade", "--team-in", "bos", "--team-out", "mia", "--value", "50"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["team_in"]["team"] == "BOS"
    assert payload["team_out"]["team"] == "MIA"
