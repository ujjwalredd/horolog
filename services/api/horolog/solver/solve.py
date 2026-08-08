"""Turn intents into a plan.

Three steps, no solver: expand recurrence into concrete requirements, place them
greedily, report what did not fit.

A CP-SAT model sat here for a while. Measured against the greedy placement it
was worth at most +0.58% on schedule quality while taking 100-2000x longer
(1-24ms vs a 2s budget), and on adversarial instances it timed out and returned
worse answers than its own starting point. It was deleted. The ordering rules in
`greedy.py` already encode every term the objective did — priority preemption,
stay-put stability, deadlines, time-of-day, fragmentation, per-day caps — and
`score.py` keeps the trade-offs measurable.
"""

from __future__ import annotations

import time

from horolog.domain.events import BusyInterval
from horolog.domain.intent import Intent
from horolog.domain.plan import Plan, ScheduledBlock, UnmetDemand
from horolog.solver.expand import expand_all
from horolog.solver.greedy import construct


def solve(
    intents: list[Intent],
    busy: list[BusyInterval],
    horizon_slots: int,
    previous: Plan | None = None,
) -> Plan:
    """Place every intent's demand around `busy`, staying close to `previous`.

    Never raises on an over-subscribed calendar: unplaceable demand comes back in
    `Plan.unmet` so the caller can show the user what did not fit.
    """
    if horizon_slots <= 0:
        raise ValueError(f"horizon_slots must be positive, got {horizon_slots}")

    started = time.perf_counter()
    requirements = expand_all(intents, horizon_slots)
    prior = previous.by_key() if previous else {}
    placement = construct(requirements, merge_busy(busy), previous=prior)

    blocks: list[ScheduledBlock] = []
    unmet: list[UnmetDemand] = []
    for ri, req in enumerate(requirements):
        placed = 0
        for chunk in range(req.n_chunks):
            found = placement.get((ri, chunk))
            if not found:
                continue
            start, size = found
            placed += size
            was = prior.get((req.intent_id, req.occurrence, chunk))
            blocks.append(
                ScheduledBlock(
                    intent_id=req.intent_id,
                    occurrence=req.occurrence,
                    chunk=chunk,
                    start_slot=start,
                    end_slot=start + size,
                    priority=req.priority,
                    moved_from=was.start_slot if was else None,
                )
            )
        if placed < req.required_slots:
            unmet.append(
                UnmetDemand(
                    intent_id=req.intent_id,
                    occurrence=req.occurrence,
                    required_slots=req.required_slots,
                    placed_slots=placed,
                    priority=req.priority,
                )
            )

    blocks.sort(key=lambda b: (b.start_slot, b.intent_id))
    return Plan(
        blocks=blocks,
        unmet=unmet,
        solve_ms=(time.perf_counter() - started) * 1000,
        horizon_slots=horizon_slots,
    )


def merge_busy(busy: list[BusyInterval]) -> list[BusyInterval]:
    """Collapse overlapping busy intervals into a disjoint union.

    Real calendars are double-booked constantly — back-to-back invites, an
    all-day event overlapping a meeting. The placer only cares which slots are
    unavailable, not how many events claim them.
    """
    if not busy:
        return []
    ordered = sorted(busy, key=lambda b: (b.start_slot, b.end_slot))
    merged = [ordered[0].model_copy()]
    for nxt in ordered[1:]:
        last = merged[-1]
        if nxt.start_slot <= last.end_slot:
            if nxt.end_slot > last.end_slot:
                last.end_slot = nxt.end_slot
                last.source_id = f"{last.source_id}+{nxt.source_id}"
                last.label = f"{last.label}+{nxt.label}".strip("+")
        else:
            merged.append(nxt.model_copy())
    return merged
