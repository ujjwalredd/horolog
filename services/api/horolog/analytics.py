"""Productivity analytics.

Derived entirely from the plan and the calendar mirror — there is no separate
event log to drift out of sync, and no tracking of anything the scheduler did
not already need to know.

Every figure here is deliberately a *measurement of the plan*, not a score. A
number a user cannot act on is decoration; each one below maps to a concrete
lever (add a window, drop an intent, decline a meeting, raise a priority).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import TypeVar

from pydantic import BaseModel, Field

from horolog.domain.events import BusyInterval
from horolog.domain.intent import Intent, IntentKind, Priority
from horolog.domain.plan import Plan
from horolog.domain.time import SLOTS_PER_DAY, slots_to_minutes

K = TypeVar("K")


class Slice(BaseModel):
    label: str
    minutes: int
    share: float = Field(ge=0, le=1)


class DayLoad(BaseModel):
    day: int
    """Days from the horizon origin."""
    scheduled_minutes: int
    meeting_minutes: int
    longest_free_run_minutes: int
    """The biggest uninterrupted gap left in the workday.

    The single most useful number on this page: a day can look survivable on
    total hours and still be useless for real work if it is diced into
    twenty-minute slivers."""


class Analytics(BaseModel):
    horizon_days: int
    window_minutes_per_day: int

    focus_minutes: int
    meeting_minutes: int
    scheduled_minutes: int
    unmet_minutes: int

    meeting_load: float = Field(ge=0)
    """Meeting time as a fraction of available working time."""

    fragmentation: float = Field(ge=0)
    """Mean scheduled block length, in minutes. Falling fragmentation with flat
    total hours means the same work is being chopped finer — the failure mode
    that makes a full calendar feel worse than it measures."""

    longest_focus_run_minutes: int
    after_hours_minutes: int
    """Real meetings sitting outside the configured workday. Not something the
    scheduler causes — something it can show you."""

    by_kind: list[Slice]
    by_priority: list[Slice]
    days: list[DayLoad]

    @property
    def deep_work_ratio(self) -> float:
        """Share of scheduled time in blocks of an hour or more."""
        return 0.0 if not self.scheduled_minutes else self.focus_minutes / self.scheduled_minutes


def _day_spans(start_slot: int, end_slot: int) -> list[tuple[int, int, int]]:
    """Split [start_slot, end_slot) into per-day (day, local_start, local_end) pieces.

    A busy event is not bounded to one day the way a solver-placed block is
    (`AllowedWindow` guarantees that; nothing does for a real calendar event) —
    an out-of-office spanning several days or a flight crossing midnight has to
    be attributed to every day it actually occupies, not dumped whole onto the
    day it starts.
    """
    out: list[tuple[int, int, int]] = []
    day = start_slot // SLOTS_PER_DAY
    cursor = start_slot
    while cursor < end_slot:
        day_end = (day + 1) * SLOTS_PER_DAY
        piece_end = min(end_slot, day_end)
        out.append((day, cursor - day * SLOTS_PER_DAY, piece_end - day * SLOTS_PER_DAY))
        cursor = piece_end
        day += 1
    return out


def _runs(occupied: list[tuple[int, int]], lo: int, hi: int) -> list[int]:
    """Lengths of the free gaps inside [lo, hi) given sorted occupied spans."""
    gaps: list[int] = []
    cursor = lo
    for start, end in occupied:
        if end <= lo or start >= hi:
            continue
        if start > cursor:
            gaps.append(start - cursor)
        cursor = max(cursor, end)
    if cursor < hi:
        gaps.append(hi - cursor)
    return [g for g in gaps if g > 0]


def analyse(
    plan: Plan,
    intents: list[Intent],
    busy: list[BusyInterval],
    horizon_days: int,
    workday_start_min: int,
    workday_end_min: int,
) -> Analytics:
    kinds = {i.id: i.kind for i in intents}
    priorities = {i.id: i.priority for i in intents}

    day_start = workday_start_min // 15
    day_end = workday_end_min // 15
    window = day_end - day_start

    kind_minutes: dict[IntentKind, int] = defaultdict(int)
    priority_minutes: dict[Priority, int] = defaultdict(int)
    per_day_scheduled: dict[int, int] = defaultdict(int)
    per_day_meeting: dict[int, int] = defaultdict(int)
    lengths: list[int] = []

    for block in plan.blocks:
        minutes = slots_to_minutes(block.slots)
        kind_minutes[kinds.get(block.intent_id, IntentKind.TASK)] += minutes
        priority_minutes[priorities.get(block.intent_id, Priority.P3)] += minutes
        per_day_scheduled[block.start_slot // SLOTS_PER_DAY] += minutes
        lengths.append(minutes)

    after_hours = 0
    for event in busy:
        minutes = slots_to_minutes(event.end_slot - event.start_slot)
        offset = event.start_slot % SLOTS_PER_DAY
        if offset < day_start or offset >= day_end:
            after_hours += minutes
        for day, day_lo, day_hi in _day_spans(event.start_slot, event.end_slot):
            per_day_meeting[day] += slots_to_minutes(day_hi - day_lo)

    occupied_by_day: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for block in plan.blocks:
        occupied_by_day[block.start_slot // SLOTS_PER_DAY].append(
            (block.start_slot % SLOTS_PER_DAY, block.end_slot % SLOTS_PER_DAY or SLOTS_PER_DAY)
        )
    for event in busy:
        for day, day_lo, day_hi in _day_spans(event.start_slot, event.end_slot):
            occupied_by_day[day].append((day_lo, day_hi))

    days: list[DayLoad] = []
    longest_overall = 0
    for day in range(horizon_days):
        spans = sorted(occupied_by_day.get(day, []))
        gaps = _runs(spans, day_start, day_end)
        # `_runs` already returns [window] itself when nothing is occupied, so
        # an empty result here means the opposite of "free all day" — the
        # occupied spans left no gap at all.
        longest = slots_to_minutes(max(gaps)) if gaps else 0
        longest_overall = max(longest_overall, longest)
        days.append(
            DayLoad(
                day=day,
                scheduled_minutes=per_day_scheduled.get(day, 0),
                meeting_minutes=per_day_meeting.get(day, 0),
                longest_free_run_minutes=longest,
            )
        )

    scheduled = sum(kind_minutes.values())
    meeting_minutes = sum(per_day_meeting.values())
    capacity = slots_to_minutes(window) * horizon_days

    def slices(source: Mapping[K, int], namer: Callable[[K], str]) -> list[Slice]:
        total = sum(source.values()) or 1
        return sorted(
            (
                Slice(label=namer(key), minutes=value, share=value / total)
                for key, value in source.items()
                if value
            ),
            key=lambda s: -s.minutes,
        )

    return Analytics(
        horizon_days=horizon_days,
        window_minutes_per_day=slots_to_minutes(window),
        focus_minutes=sum(m for m in lengths if m >= 60),
        meeting_minutes=meeting_minutes,
        scheduled_minutes=scheduled,
        unmet_minutes=sum(slots_to_minutes(u.shortfall_slots) for u in plan.unmet),
        meeting_load=meeting_minutes / capacity if capacity else 0.0,
        fragmentation=sum(lengths) / len(lengths) if lengths else 0.0,
        longest_focus_run_minutes=longest_overall,
        after_hours_minutes=after_hours,
        by_kind=slices(kind_minutes, lambda k: k.value),
        by_priority=slices(priority_minutes, lambda p: f"P{int(p)}"),
        days=days,
    )
