"""Solver properties.

These are the checks that fail if the scheduling engine breaks. Everything else
in the product is I/O around this.
"""

from __future__ import annotations

import random
from itertools import pairwise

import pytest

from horolog.domain.events import BusyInterval
from horolog.domain.intent import DailyWindow, EnergyLevel, Intent, IntentKind, Priority
from horolog.domain.plan import Plan
from horolog.domain.time import SLOTS_PER_DAY, SLOTS_PER_HOUR, minutes_to_slots
from horolog.solver.expand import expand
from horolog.solver.solve import merge_busy, solve

WEEK = 7 * SLOTS_PER_DAY


def at(day: int, hour: int) -> int:
    return day * SLOTS_PER_DAY + hour * SLOTS_PER_HOUR


def workday(start_h: int = 9, end_h: int = 17) -> list[DailyWindow]:
    return [DailyWindow(start_min=start_h * 60, end_min=end_h * 60)]


def task(
    ident: str = "t1",
    minutes: int = 120,
    priority: Priority = Priority.P3,
    min_chunk: int = 60,
    max_chunk: int = 120,
    **kw: object,
) -> Intent:
    return Intent(
        id=ident,
        kind=IntentKind.TASK,
        title=ident,
        priority=priority,
        minutes_per_period=minutes,
        min_chunk_minutes=min_chunk,
        max_chunk_minutes=max_chunk,
        daily_windows=kw.pop("daily_windows", workday()),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


def assert_sound(plan: Plan, busy: list[BusyInterval]) -> None:
    """Invariants that must hold for any plan the solver ever returns."""
    ordered = sorted(plan.blocks, key=lambda b: b.start_slot)
    for a, b in pairwise(ordered):
        assert a.end_slot <= b.start_slot, f"blocks overlap: {a} / {b}"
    for block in plan.blocks:
        assert block.end_slot > block.start_slot
        assert block.end_slot <= plan.horizon_slots
        for occupied in busy:
            assert not (
                block.start_slot < occupied.end_slot and occupied.start_slot < block.end_slot
            ), f"block {block} overlaps busy {occupied}"


def test_places_full_duration_on_an_empty_calendar() -> None:
    intent = task(minutes=120)
    plan = solve([intent], [], WEEK)

    assert_sound(plan, [])
    assert sum(b.slots for b in plan.blocks) == minutes_to_slots(120)
    assert not plan.unmet


def test_blocks_stay_inside_their_window() -> None:
    """A block must sit wholly within one window — never straddle a gap."""
    lunch_split = [
        DailyWindow(start_min=9 * 60, end_min=12 * 60),
        DailyWindow(start_min=13 * 60, end_min=17 * 60),
    ]
    intent = task(minutes=180, min_chunk=180, max_chunk=180, daily_windows=lunch_split)
    plan = solve([intent], [], WEEK)

    assert plan.blocks
    for block in plan.blocks:
        day = block.start_slot // SLOTS_PER_DAY
        in_morning = block.start_slot >= at(day, 9) and block.end_slot <= at(day, 12)
        in_afternoon = block.start_slot >= at(day, 13) and block.end_slot <= at(day, 17)
        assert in_morning or in_afternoon, f"{block} straddles the lunch gap"


def test_never_schedules_over_a_real_meeting() -> None:
    """Reclaim's hard rule: no intent, at any priority, displaces a real event."""
    busy = [
        BusyInterval(source_id=f"m{d}", start_slot=at(d, 9), end_slot=at(d, 17)) for d in range(7)
    ]
    intent = task(minutes=120, priority=Priority.P1)
    plan = solve([intent], busy, WEEK)

    assert_sound(plan, busy)
    assert not plan.blocks
    assert plan.unmet and plan.unmet[0].shortfall_slots == minutes_to_slots(120)


def test_higher_priority_wins_a_contested_slot() -> None:
    """Preemption is priced, not ruled: P1 outbids P4 for the only hour there is."""
    only_an_hour = [DailyWindow(start_min=10 * 60, end_min=11 * 60)]
    critical = task("critical", 60, Priority.P1, 60, 60, daily_windows=only_an_hour)
    trivial = task("trivial", 60, Priority.P4, 60, 60, daily_windows=only_an_hour)

    plan = solve([critical, trivial], [], SLOTS_PER_DAY)

    assert_sound(plan, [])
    scheduled = {b.intent_id for b in plan.blocks}
    assert scheduled == {"critical"}
    assert [u.intent_id for u in plan.unmet] == ["trivial"]


def test_high_energy_wins_a_contested_slot_among_equals() -> None:
    """Same priority, same kind, one open hour: the demanding one goes first.

    This is the only place `energy` is allowed to have any effect at all - it
    must never override priority or kind, only break a tie between them."""
    only_an_hour = [DailyWindow(start_min=10 * 60, end_min=11 * 60)]
    demanding = task(
        "demanding", 60, Priority.P3, 60, 60, daily_windows=only_an_hour, energy=EnergyLevel.HIGH
    )
    ordinary = task("ordinary", 60, Priority.P3, 60, 60, daily_windows=only_an_hour)

    plan = solve([demanding, ordinary], [], SLOTS_PER_DAY)

    assert_sound(plan, [])
    scheduled = {b.intent_id for b in plan.blocks}
    assert scheduled == {"demanding"}
    assert [u.intent_id for u in plan.unmet] == ["ordinary"]


def test_resolve_with_nothing_changed_is_a_fixed_point() -> None:
    """The headline stability guarantee: re-planning an unchanged week changes nothing.

    This is exactly what Motion is criticised for failing — open the app, and the
    calendar has quietly rearranged itself. Here it must be a no-op, to the slot.
    """
    intents = [task(f"t{i}", 120, Priority.P3) for i in range(5)]
    busy = [BusyInterval(source_id="standup", start_slot=at(2, 10), end_slot=at(2, 11))]

    first = solve(intents, busy, WEEK)
    again = solve(intents, busy, WEEK, previous=first)

    assert again.perturbation_slots == 0
    assert {k: b.start_slot for k, b in again.by_key().items()} == {
        k: b.start_slot for k, b in first.by_key().items()
    }


def test_a_new_meeting_disturbs_only_its_neighbourhood() -> None:
    """A meeting lands on day 5; the rest of the week must stay put.

    Blocks the meeting actually collides with have to move. One further block may
    shift as a knock-on effect of re-packing the day they land on — minimal
    perturbation is minimal in aggregate, not per block. Anything beyond that is
    the thrash this design exists to prevent.
    """
    intents = [task(f"t{i}", 120, Priority.P3) for i in range(5)]
    first = solve(intents, [], WEEK)
    assert first.blocks

    intrusion = BusyInterval(source_id="offsite", start_slot=at(5, 9), end_slot=at(5, 17))
    second = solve(intents, [intrusion], WEEK, previous=first)
    assert_sound(second, [intrusion])

    displaced = sum(
        1
        for b in first.blocks
        if b.start_slot < intrusion.end_slot and intrusion.start_slot < b.end_slot
    )
    after = second.by_key()
    moved = sum(1 for k, b in first.by_key().items() if after[k].start_slot != b.start_slot)

    assert len(after) == len(first.blocks), "no block may be dropped by a re-solve"
    assert moved <= displaced + 1, (
        f"{moved} blocks moved but only {displaced} were displaced — "
        "the re-solve is cascading instead of staying local"
    )


def test_oversubscription_reports_shortfall_instead_of_failing() -> None:
    """An impossible week is a fact to surface, not an exception to raise."""
    intents = [task(f"t{i}", 480, Priority.P3, 60, 480) for i in range(20)]
    plan = solve(intents, [], WEEK)

    assert_sound(plan, [])
    assert plan.unmet, "an over-subscribed calendar must report unmet demand"


def test_oversized_task_splits_into_bounded_chunks() -> None:
    """A task bigger than one max_chunk must split into multiple blocks, each
    within [min_chunk, max_chunk], with nothing left unmet on an empty calendar."""
    intent = task("big", minutes=360, min_chunk=60, max_chunk=120)  # 3x max_chunk
    plan = solve([intent], [], WEEK)

    assert_sound(plan, [])
    mine = [b for b in plan.blocks if b.intent_id == "big"]
    assert len(mine) > 1, "a 360-minute task at max_chunk=120 must split into more than one block"
    for block in mine:
        assert minutes_to_slots(60) <= block.slots <= minutes_to_slots(120)
    assert sum(b.slots for b in mine) == minutes_to_slots(360)
    assert not plan.unmet


def test_habit_repeats_once_per_period() -> None:
    gym = Intent(
        id="gym",
        kind=IntentKind.HABIT,
        title="gym",
        minutes_per_period=180,
        period_days=7,
        min_chunk_minutes=60,
        max_chunk_minutes=60,
        max_per_day=1,
        daily_windows=[DailyWindow(start_min=10 * 60, end_min=16 * 60)],
    )
    plan = solve([gym], [], 3 * WEEK)

    assert {b.occurrence for b in plan.blocks} == {0, 1, 2}, "one occurrence per week"
    for occurrence in (0, 1, 2):
        days = [b.start_slot // SLOTS_PER_DAY for b in plan.blocks if b.occurrence == occurrence]
        assert len(days) == len(set(days)), "max_per_day=1 violated"


def test_due_date_pulls_work_earlier() -> None:
    urgent = task("urgent", 120, due_slot=at(1, 17))
    plan = solve([urgent], [], WEEK)

    assert plan.blocks
    assert max(b.end_slot for b in plan.blocks) <= at(1, 17)


def test_merge_busy_unions_double_bookings() -> None:
    """Double-booked calendars are normal input, not an error."""
    merged = merge_busy(
        [
            BusyInterval(source_id="a", start_slot=10, end_slot=20),
            BusyInterval(source_id="b", start_slot=15, end_slot=30),
            BusyInterval(source_id="c", start_slot=40, end_slot=50),
        ]
    )
    assert [(b.start_slot, b.end_slot) for b in merged] == [(10, 30), (40, 50)]


def test_double_booked_calendar_still_solves() -> None:
    busy = [
        BusyInterval(source_id="a", start_slot=at(0, 9), end_slot=at(0, 12)),
        BusyInterval(source_id="b", start_slot=at(0, 10), end_slot=at(0, 14)),
    ]
    plan = solve([task(minutes=60)], busy, WEEK)

    assert_sound(plan, busy)


def test_expand_emits_whole_periods_only() -> None:
    """A partial trailing week must not manufacture a permanent shortfall."""
    gym = Intent(
        id="gym",
        kind=IntentKind.HABIT,
        title="gym",
        minutes_per_period=60,
        period_days=7,
        min_chunk_minutes=60,
        max_chunk_minutes=60,
    )
    assert len(expand(gym, WEEK + 3 * SLOTS_PER_DAY)) == 1


def test_stays_sound_on_adversarial_input() -> None:
    """Fragmented windows, deadlines, per-day caps, preferences, heavy meetings.

    The placement heuristics are the only engine now, so the shapes that would
    have been caught by a solver proving feasibility have to be caught here.
    """
    rng = random.Random(7)
    intents: list[Intent] = []
    for i in range(60):
        kind = rng.choice([IntentKind.TASK, IntentKind.HABIT, IntentKind.FOCUS])
        morning = rng.choice([8, 9, 10])
        afternoon = rng.choice([13, 14, 15])
        minutes = rng.choice([30, 60, 90])
        intents.append(
            Intent(
                id=f"h{i}",
                kind=kind,
                title=f"h{i}",
                priority=Priority(rng.randint(1, 4)),
                minutes_per_period=minutes,
                period_days=7 if kind is not IntentKind.TASK else None,
                min_chunk_minutes=30,
                max_chunk_minutes=minutes,
                max_per_day=1 if rng.random() < 0.5 else None,
                due_slot=at(rng.randint(3, 10), 17) if kind is IntentKind.TASK else None,
                preferred_start_min=rng.choice([None, morning * 60, afternoon * 60]),
                daily_windows=[
                    DailyWindow(start_min=morning * 60, end_min=(morning + 2) * 60),
                    DailyWindow(start_min=afternoon * 60, end_min=(afternoon + 3) * 60),
                ],
            )
        )
    busy = [
        BusyInterval(source_id=f"m{d}_{h}", start_slot=at(d, h), end_slot=at(d, h) + 2)
        for d in range(14)
        for h in rng.sample(range(8, 17), 4)
    ]

    plan = solve(intents, merge_busy(busy), 2 * WEEK)
    assert_sound(plan, merge_busy(busy))
    assert plan.blocks, "an adversarial but satisfiable calendar must still schedule work"

    # And it must still be a fixed point: churn under pressure is the failure
    # mode that matters, because that is when a user is watching.
    again = solve(intents, merge_busy(busy), 2 * WEEK, previous=plan)
    assert again.perturbation_slots == 0


def test_rejects_an_intent_that_could_never_fit_its_window() -> None:
    with pytest.raises(ValueError, match="shorter than min_chunk"):
        task(minutes=120, min_chunk=120, daily_windows=[DailyWindow(start_min=600, end_min=630)])


def test_a_busy_week_does_not_cascade() -> None:
    """The stability guarantee has to hold at realistic scale, not just at five
    blocks.

    A single-pass greedy that merely *prefers* a chunk's old slot fails here:
    displaced blocks are reallocated in priority order, so they reach the
    allocator before untouched blocks and evict them, and the loss cascades.
    Reserving prior placements before reallocating anything is what bounds it.
    """
    intents = [task(f"t{i}", 120, Priority.P3, 120, 120) for i in range(20)]
    first = solve(intents, [], WEEK)
    assert len(first.blocks) == 20

    intrusion = BusyInterval(source_id="offsite", start_slot=at(1, 9), end_slot=at(1, 17))
    second = solve(intents, [intrusion], WEEK, previous=first)
    assert_sound(second, [intrusion])

    displaced = sum(
        1
        for b in first.blocks
        if b.start_slot < intrusion.end_slot and intrusion.start_slot < b.end_slot
    )
    after = second.by_key()
    moved = sum(1 for k, b in first.by_key().items() if after[k].start_slot != b.start_slot)

    assert displaced > 0, "the fixture must actually displace something"
    assert moved <= displaced, (
        f"{moved} blocks moved but only {displaced} were displaced — "
        "the re-solve is cascading across untouched work"
    )
