"""Solve-time and quality benchmark.

    python -m horolog.bench

Quality is reported via `score.py`, which is a metric rather than an objective —
nothing optimises it. Its purpose is regression detection: change a placement
rule, re-run this, and see whether schedules got better or worse.
"""

from __future__ import annotations

import random
import statistics

from horolog.domain.events import BusyInterval
from horolog.domain.intent import DailyWindow, Intent, IntentKind, Priority
from horolog.domain.time import SLOT_MINUTES, SLOTS_PER_DAY, SLOTS_PER_HOUR
from horolog.solver.expand import expand_all
from horolog.solver.greedy import construct
from horolog.solver.score import score
from horolog.solver.solve import merge_busy, solve

HORIZON = 21 * SLOTS_PER_DAY
REPEATS = 7
DAY_START_H, DAY_END_H = 9, 18
UTILISATION = 0.85
"""Demand as a fraction of open capacity, held fixed across intent counts.

A fixed per-intent duration would make 300 intents ask for 5x more time than the
horizon contains, and the benchmark would measure how fast an impossible week is
rejected rather than how fast a realistic one is scheduled.
"""


def _capacity_slots() -> int:
    return 21 * (DAY_END_H - DAY_START_H) * SLOTS_PER_HOUR


def _population(count: int, seed: int) -> list[Intent]:
    rng = random.Random(seed)
    kinds = [IntentKind.TASK, IntentKind.HABIT, IntentKind.FOCUS]
    # A periodic intent recurs 3x over 21 days, so it costs 3x its stated
    # duration; weight the budget accordingly.
    weight = sum(1 if kinds[i % len(kinds)] is IntentKind.TASK else 3 for i in range(count))
    budget_min = _capacity_slots() * SLOT_MINUTES * UTILISATION
    per_intent = max(SLOT_MINUTES * 2, int(budget_min / weight))

    out: list[Intent] = []
    for i in range(count):
        kind = kinds[i % len(kinds)]
        minutes = max(30, round(per_intent * rng.uniform(0.6, 1.4) / 30) * 30)
        out.append(
            Intent(
                id=f"i{i}",
                kind=kind,
                title=f"intent {i}",
                priority=Priority(rng.randint(1, 4)),
                minutes_per_period=minutes,
                period_days=7 if kind is not IntentKind.TASK else None,
                min_chunk_minutes=30,
                max_chunk_minutes=min(minutes, 120),
                daily_windows=[DailyWindow(start_min=DAY_START_H * 60, end_min=DAY_END_H * 60)],
            )
        )
    return out


def _meetings(seed: int) -> list[BusyInterval]:
    rng = random.Random(seed + 1)
    out: list[BusyInterval] = []
    for day in range(21):
        for j in range(rng.randint(1, 4)):
            hour = rng.randint(9, 16)
            start = day * SLOTS_PER_DAY + hour * SLOTS_PER_HOUR
            out.append(
                BusyInterval(source_id=f"m{day}_{hour}_{j}", start_slot=start, end_slot=start + 2)
            )
    return out


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=100)[94] if len(values) > 1 else values[0]


def main() -> None:
    print(f"horizon {HORIZON} slots (21 days), {DAY_START_H}:00-{DAY_END_H}:00 workday")
    print(f"demand held at {UTILISATION:.0%} of open capacity | {REPEATS} runs each\n")
    print(
        f"{'intents':>8} {'reqs':>6} {'load':>6} {'blocks':>7} {'cold p50':>9} "
        f"{'cold p95':>9} {'warm p50':>9} {'warm p95':>9} {'unmet':>6} {'churn':>6}"
    )
    for count in (30, 100, 300):
        cold: list[float] = []
        warm: list[float] = []
        churn: list[int] = []
        plan = None
        for seed in range(REPEATS):
            intents, busy = _population(count, seed), _meetings(seed)
            plan = solve(intents, busy, HORIZON)
            cold.append(plan.solve_ms)
            nudge = 5 * SLOTS_PER_DAY + 40
            extra = BusyInterval(source_id="new", start_slot=nudge, end_slot=nudge + 8)
            after = solve(intents, [*busy, extra], HORIZON, previous=plan)
            warm.append(after.solve_ms)
            churn.append(after.perturbation_slots)

        assert plan is not None
        reqs = expand_all(_population(count, 0), HORIZON)
        demand = sum(r.required_slots for r in reqs)
        print(
            f"{count:>8} {len(reqs):>6} {demand / _capacity_slots():>5.0%} "
            f"{len(plan.blocks):>7} {statistics.median(cold):>8.1f}ms {_p95(cold):>8.1f}ms "
            f"{statistics.median(warm):>8.1f}ms {_p95(warm):>8.1f}ms "
            f"{len(plan.unmet):>6} {statistics.median(churn):>6.0f}"
        )

    print("\nquality (score.py metric, higher is better):")
    for count in (30, 100, 300):
        intents, busy = _population(count, 0), merge_busy(_meetings(0))
        reqs = expand_all(intents, HORIZON)
        print(f"  {count:>4} intents -> {score(reqs, construct(reqs, busy)):>12,}")


if __name__ == "__main__":
    main()
