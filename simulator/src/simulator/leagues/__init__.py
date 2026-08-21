"""League configs. Each module exposes a LEAGUE dict (see nba.py) shaped
the same way, so the engine (simulate.py/bracket.py/ratings.py) stays
league-agnostic per docs/PRD.md section 9. NFL would be added here as
nfl.py in Phase 3.
"""

from . import nba

LEAGUES = {
    "nba": nba.LEAGUE,
}
