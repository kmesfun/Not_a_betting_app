"""Formats a simulation batch into the "today's update" payload.

PRD reference: docs/PRD.md P0.6. The callable interface serves this
precomputed payload -- it does not run a new simulation per request (see
the P0.6 latency NFR added in the PRD revision).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .simulate import SimulationBatchResult


def build_update(
    league_name: str,
    result: SimulationBatchResult,
    as_of: datetime | None = None,
    team: str | None = None,
) -> dict:
    as_of = as_of or datetime.now(timezone.utc)
    payload = {
        "league": league_name,
        "as_of": as_of.isoformat(),
        "n_sims": result.n_sims,
    }

    if team is not None:
        if team not in result.teams:
            raise KeyError(f"Unknown team: {team}")
        payload["team"] = result.teams[team].as_dict()
        return payload

    payload["teams"] = [t.as_dict() for t in result.sorted_by_championship()]
    return payload
