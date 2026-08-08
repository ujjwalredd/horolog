"""Intent -> Requirement expansion.

Recurrence and time-of-day windows are resolved to absolute slot ranges *here*,
so the CP model never reasons about calendars, periods or midnight. That split is
what keeps `model.py` a pure interval-scheduling problem.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from horolog.domain.intent import Intent, IntentKind, Priority
from horolog.domain.time import SLOT_MINUTES, SLOTS_PER_DAY, day_start

MAX_CHUNKS_PER_REQUIREMENT = 16
# ponytail: hard cap so a pathological intent (8h at 15-min chunks) cannot blow up
# the model. Raise it if anyone legitimately needs finer splitting.

SCHEDULING_RANGE_DAYS = 14
"""How far ahead a single requirement may be placed, from its own start.

Each candidate day costs the model a boolean per chunk, so an unbounded horizon
makes a 12-week calendar quadratically harder to solve than a 2-week one for no
user-visible benefit — nobody needs to know which Tuesday in November a task
lands on. Reclaim meters the same thing as a plan feature ("scheduling range",
1/8/12 weeks); here it exists to keep the model small.
"""


class AllowedWindow(BaseModel):
    """A contiguous absolute span a chunk may occupy, entirely within one day."""

    lo: int
    hi: int
    day: int

    @property
    def span(self) -> int:
        return self.hi - self.lo


class Requirement(BaseModel):
    """One period's worth of demand from one intent."""

    intent_id: str
    kind: IntentKind
    occurrence: int
    priority: Priority
    required_slots: int = Field(gt=0)
    min_chunk: int = Field(gt=0)
    max_chunk: int = Field(gt=0)
    max_per_day: int | None = None
    windows: list[AllowedWindow]
    due_slot: int | None = None
    preferred_offset: int | None = None
    """Preferred start as slots from midnight, or None."""

    blocked: list[tuple[int, int]] = Field(default_factory=list)
    """Spans only this requirement must avoid — see `Intent.blocked_slots`."""

    @property
    def n_chunks(self) -> int:
        """How many chunk variables to allocate.

        Upper bound is `required // min_chunk` — any more could not all be
        present without exceeding the requirement.
        """
        return max(1, min(self.required_slots // self.min_chunk, MAX_CHUNKS_PER_REQUIREMENT))

    @property
    def capacity_slots(self) -> int:
        """Total schedulable time across all windows. Cheap infeasibility signal."""
        return sum(w.span for w in self.windows)


def _windows_for(intent: Intent, lo: int, hi: int) -> list[AllowedWindow]:
    """Absolute windows for [lo, hi), one per (day x daily_window), clipped."""
    if hi <= lo:
        return []
    windows: list[AllowedWindow] = []
    first_day, last_day = lo // SLOTS_PER_DAY, (hi - 1) // SLOTS_PER_DAY
    # An intent with no stated preference may use any hour of the day.
    spans = (
        [(w.start_min // SLOT_MINUTES, w.end_min // SLOT_MINUTES) for w in intent.daily_windows]
        if intent.daily_windows
        else [(0, SLOTS_PER_DAY)]
    )
    for day in range(first_day, last_day + 1):
        base = day_start(day)
        for start_off, end_off in spans:
            w_lo, w_hi = max(base + start_off, lo), min(base + end_off, hi)
            # Drop windows too short to hold even one chunk — they only add
            # variables the solver must prove useless.
            if w_hi - w_lo >= intent.min_chunk_slots:
                windows.append(AllowedWindow(lo=w_lo, hi=w_hi, day=day))
    return windows


def expand(intent: Intent, horizon_slots: int) -> list[Requirement]:
    """Expand one intent into its per-period requirements over the horizon."""
    lo = max(0, intent.earliest_slot or 0)
    # Deliberately NOT clipped to due_slot. Clipping would make late placement
    # structurally impossible, which sounds tidy but silently converts "this
    # slipped to Saturday" into "this vanished". The due date is enforced as a
    # priced objective term instead, so an overloaded week degrades honestly.
    hi = horizon_slots
    if hi <= lo:
        return []

    preferred = (
        intent.preferred_start_min // SLOT_MINUTES
        if intent.preferred_start_min is not None
        else None
    )

    def build(occurrence: int, p_lo: int, p_hi: int) -> Requirement | None:
        reach = min(p_hi, p_lo + SCHEDULING_RANGE_DAYS * SLOTS_PER_DAY)
        windows = _windows_for(intent, p_lo, reach)
        if not windows:
            return None
        return Requirement(
            intent_id=intent.id,
            kind=intent.kind,
            occurrence=occurrence,
            priority=intent.priority,
            required_slots=intent.required_slots,
            min_chunk=intent.min_chunk_slots,
            max_chunk=intent.max_chunk_slots,
            max_per_day=intent.max_per_day,
            windows=windows,
            due_slot=intent.due_slot,
            preferred_offset=preferred,
            blocked=list(intent.blocked_slots),
        )

    if intent.period_days is None:
        one = build(0, lo, hi)
        return [one] if one else []

    period = intent.period_days * SLOTS_PER_DAY
    out: list[Requirement] = []
    cursor, occurrence = lo, 0
    # Only whole periods are emitted. A partial trailing week would otherwise
    # report a permanent shortfall for time the user never actually asked for.
    while cursor + period <= hi:
        req = build(occurrence, cursor, cursor + period)
        if req:
            out.append(req)
        cursor += period
        occurrence += 1
    return out


def expand_all(intents: list[Intent], horizon_slots: int) -> list[Requirement]:
    return [r for intent in intents for r in expand(intent, horizon_slots)]
