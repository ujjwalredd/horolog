"""Solver output contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from horolog.domain.intent import Priority


class ScheduledBlock(BaseModel):
    intent_id: str
    occurrence: int
    """Which repetition of a periodic intent this belongs to (0 for one-shots)."""
    chunk: int
    start_slot: int = Field(ge=0)
    end_slot: int
    priority: Priority
    moved_from: int | None = None
    """Previous start slot, when this block existed in the prior plan."""

    @model_validator(mode="after")
    def _ordered(self) -> ScheduledBlock:
        if self.end_slot <= self.start_slot:
            raise ValueError(f"end_slot {self.end_slot} must exceed start_slot {self.start_slot}")
        return self

    @property
    def key(self) -> tuple[str, int, int]:
        return (self.intent_id, self.occurrence, self.chunk)

    @property
    def slots(self) -> int:
        return self.end_slot - self.start_slot


class UnmetDemand(BaseModel):
    """Time that was asked for and could not be placed.

    Reported rather than silently dropped — an over-subscribed week is a fact the
    user needs to see, not an error to swallow.
    """

    intent_id: str
    occurrence: int
    required_slots: int
    placed_slots: int
    priority: Priority

    @property
    def shortfall_slots(self) -> int:
        return self.required_slots - self.placed_slots


class Plan(BaseModel):
    """A complete placement. There is no status field: a plan is always feasible
    by construction, and everything that did not fit is named in `unmet`."""

    blocks: list[ScheduledBlock] = Field(default_factory=list)
    unmet: list[UnmetDemand] = Field(default_factory=list)
    solve_ms: float = 0.0
    horizon_slots: int = 0

    @property
    def complete(self) -> bool:
        return not self.unmet

    def by_key(self) -> dict[tuple[str, int, int], ScheduledBlock]:
        return {b.key: b for b in self.blocks}

    @property
    def perturbation_slots(self) -> int:
        """Total distance every block travelled versus the previous plan.

        The headline stability number (plan §1.3): this is the objective's
        minimal-perturbation term, made observable.
        """
        return sum(
            abs(b.start_slot - b.moved_from) for b in self.blocks if b.moved_from is not None
        )
