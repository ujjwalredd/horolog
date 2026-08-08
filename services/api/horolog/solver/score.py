"""Plan quality as a single number.

This is a *metric*, not an optimisation target — nothing maximises it. It exists
so that changes to the placement heuristics can be measured instead of argued
about: run the benchmark before and after, and see whether schedules got better
or worse.

The weights encode the same trade-offs the ordering rules in `greedy.py` apply,
which is what makes the number meaningful: if the two ever disagree, one of them
is wrong.
"""

from __future__ import annotations

from itertools import pairwise

from pydantic import BaseModel, model_validator

from horolog.domain.intent import KIND_RANK, Priority
from horolog.solver.expand import Requirement
from horolog.solver.greedy import Placement


class Weights(BaseModel):
    """Scoring coefficients. Tunable, but the invariants below must hold."""

    place: dict[Priority, int] = {
        Priority.P1: 20_000,
        Priority.P2: 8_000,
        Priority.P3: 4_000,
        Priority.P4: 2_000,
    }
    """Reward per slot placed. The P1:P4 ratio *is* preemption — a critical block
    is worth ten low-priority ones, so displacing them to fit it is an
    improvement rather than a rule."""

    kind_tiebreak: int = 10
    """Per rank of KIND_RANK, breaking ties within a priority tier: meetings,
    then habits, then tasks. Must stay far below the gap between tiers."""

    fragment: int = 100
    """Per block. Two long blocks beat four short ones."""

    perturb: int = 10
    """Per slot a block moved from its previous position, capped."""

    perturb_cap: int = 96
    """One day. Past that the user has already registered "it moved"; charging
    more would let stability outrank getting work scheduled at all."""

    @model_validator(mode="after")
    def _invariants(self) -> Weights:
        cheapest = min(self.place.values())
        if cheapest <= self.fragment:
            raise ValueError(
                f"place weight {cheapest} must exceed fragment {self.fragment}, else "
                "leaving low-priority work unscheduled would score better than placing it"
            )
        tiers = sorted(self.place.values())
        smallest_gap = min(b - a for a, b in pairwise(tiers))
        if self.kind_tiebreak * max(KIND_RANK.values()) >= smallest_gap:
            raise ValueError(
                f"kind_tiebreak {self.kind_tiebreak} could outrank a priority tier "
                f"(smallest gap {smallest_gap})"
            )
        if self.perturb * self.perturb_cap >= cheapest * _MIN_SANE_CHUNK_SLOTS:
            raise ValueError(
                f"perturb x perturb_cap = {self.perturb * self.perturb_cap} exceeds the "
                f"reward for the smallest sane block; stability would outrank scheduling"
            )
        return self


_MIN_SANE_CHUNK_SLOTS = 2
"""30 minutes — the shortest block anyone schedules on purpose. Used only to
sanity-check weight calibration."""


def score(
    requirements: list[Requirement],
    placement: Placement,
    previous_starts: dict[tuple[str, int, int], int] | None = None,
    weights: Weights | None = None,
) -> int:
    """Score a placement: reward for time placed, penalties for churn and splits."""
    weights = weights or Weights()
    previous_starts = previous_starts or {}
    total = 0
    for ri, req in enumerate(requirements):
        per_slot = weights.place[req.priority] - weights.kind_tiebreak * KIND_RANK[req.kind]
        for chunk in range(req.n_chunks):
            found = placement.get((ri, chunk))
            if not found:
                continue
            start, size = found
            total += per_slot * size - weights.fragment
            was = previous_starts.get((req.intent_id, req.occurrence, chunk))
            if was is not None:
                total -= weights.perturb * min(abs(start - was), weights.perturb_cap)
    return total
