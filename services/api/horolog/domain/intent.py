"""The single scheduling primitive.

Focus Time, Habits, Tasks, Buffers and Smart Meetings are one activity type under
five names (see plan §1.2 — SelfPlanner models exactly this as a COP). `kind` is
carried for presentation and for tie-breaking only; the solver reads the numeric
fields and nothing else. Adding a sixth feature means adding a `kind` and a
factory, never a new solver path.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field, model_validator

from horolog.domain.time import SLOT_MINUTES, minutes_to_slots


class Priority(IntEnum):
    """P1 (critical) .. P4 (low). Lower value = more important, matching Reclaim."""

    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4


class EnergyLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IntentKind(StrEnum):
    TASK = "task"
    HABIT = "habit"
    FOCUS = "focus"
    BUFFER = "buffer"
    MEETING = "meeting"


# Tie-break order when priorities are equal, mirroring Reclaim's documented
# behaviour: Smart Meetings first, then Habits, then Tasks.
KIND_RANK: dict[IntentKind, int] = {
    IntentKind.MEETING: 0,
    IntentKind.BUFFER: 1,
    IntentKind.HABIT: 2,
    IntentKind.FOCUS: 3,
    IntentKind.TASK: 4,
}


class DailyWindow(BaseModel):
    """An allowed time-of-day range, in minutes from local midnight."""

    start_min: int = Field(ge=0, le=24 * 60)
    end_min: int = Field(ge=0, le=24 * 60)

    @model_validator(mode="after")
    def _ordered(self) -> DailyWindow:
        if self.end_min <= self.start_min:
            raise ValueError(f"window end {self.end_min} must exceed start {self.start_min}")
        return self


class Intent(BaseModel):
    """A demand for time that the solver must satisfy."""

    id: str
    kind: IntentKind
    title: str
    priority: Priority = Priority.P3
    energy: EnergyLevel | None = None

    # How much time, over what repeating period.
    minutes_per_period: int = Field(gt=0)
    period_days: int | None = Field(default=None, gt=0)
    """None = a one-shot demand (a task). 7 = "per week" (a habit, focus goal)."""

    # Chunking. Equal min/max means non-interruptible.
    min_chunk_minutes: int = Field(gt=0)
    max_chunk_minutes: int = Field(gt=0)
    max_per_day: int | None = Field(default=None, gt=0)

    # Where in the day it may land. Empty = anywhere.
    daily_windows: list[DailyWindow] = Field(default_factory=list)

    # Absolute bounds, as slots from the horizon origin.
    earliest_slot: int | None = None
    due_slot: int | None = None

    preferred_start_min: int | None = Field(default=None, ge=0, le=24 * 60)
    """Time-of-day the user would rather this land at. A soft objective term."""

    blocked_slots: list[tuple[int, int]] = Field(default_factory=list)
    """Spans this intent alone may not occupy — the union of the other
    attendees' busy time for a Smart Meeting.

    Kept per-intent rather than folded into the global busy list because these
    are not *your* commitments: a colleague's 2pm meeting must stop this one
    meeting landing at 2pm, while leaving 2pm perfectly available for your own
    focus time. Merging the two would quietly blank out your calendar with
    other people's schedules."""

    @model_validator(mode="after")
    def _coherent(self) -> Intent:
        if self.max_chunk_minutes < self.min_chunk_minutes:
            raise ValueError(
                f"max_chunk {self.max_chunk_minutes} < min_chunk {self.min_chunk_minutes}"
            )
        if self.minutes_per_period < self.min_chunk_minutes:
            raise ValueError(
                f"minutes_per_period {self.minutes_per_period} is smaller than one "
                f"min chunk ({self.min_chunk_minutes}); it could never be placed"
            )
        for field in ("minutes_per_period", "min_chunk_minutes", "max_chunk_minutes"):
            value: int = getattr(self, field)
            if value % SLOT_MINUTES:
                raise ValueError(f"{field}={value} must be a multiple of {SLOT_MINUTES} minutes")
        if (
            self.earliest_slot is not None
            and self.due_slot is not None
            and self.due_slot <= self.earliest_slot
        ):
            raise ValueError(f"due_slot {self.due_slot} must exceed earliest_slot")
        for window in self.daily_windows:
            span = window.end_min - window.start_min
            if span < self.min_chunk_minutes:
                raise ValueError(
                    f"window {window.start_min}-{window.end_min} is {span}min, shorter "
                    f"than min_chunk {self.min_chunk_minutes}; nothing could fit in it"
                )
        return self

    @property
    def required_slots(self) -> int:
        return minutes_to_slots(self.minutes_per_period)

    @property
    def min_chunk_slots(self) -> int:
        return minutes_to_slots(self.min_chunk_minutes)

    @property
    def max_chunk_slots(self) -> int:
        return minutes_to_slots(self.max_chunk_minutes)
