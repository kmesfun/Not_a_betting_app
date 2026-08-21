"""League config for the NBA. Team ratings are mock seed values (Elo-style,
centered at 1500) standing in for a real provider feed until the data-licensing
question in docs/PRD.md section 1a is resolved. See simulator/src/simulator/mock_data.py.
"""

LEAGUE = {
    "name": "NBA",
    "playoff_teams_per_conference": 8,
    "series_best_of": 7,
    "home_advantage_elo": 100,
    "conferences": {
        "East": [
            "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND",
            "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS",
        ],
        "West": [
            "DAL", "DEN", "GSW", "HOU", "LAC", "LAL", "MEM", "MIN",
            "NOP", "OKC", "PHX", "POR", "SAC", "SAS", "UTA",
        ],
    },
}


def all_teams() -> list[str]:
    teams: list[str] = []
    for roster in LEAGUE["conferences"].values():
        teams.extend(roster)
    return teams


def conference_of(team: str) -> str:
    for conf, roster in LEAGUE["conferences"].items():
        if team in roster:
            return conf
    raise KeyError(f"Unknown team: {team}")
