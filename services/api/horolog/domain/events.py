"""Events the solver must schedule *around* rather than place."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Transparency(StrEnum):
    FREE = "free"
    BUSY = "busy"


class BusyInterval(BaseModel):
    """A hard, immovable occupation of time.

    Two things become one of these: real calendar events the user did not create
    through us, and our own blocks that have been locked. Both are absolute — the
    solver may never place work over them. This is what enforces Reclaim's rule
    that no habit or task may ever displace a real meeting.
    """

    source_id: str
    start_slot: int = Field(ge=0)
    end_slot: int
    label: str = ""

    @model_validator(mode="after")
    def _ordered(self) -> BusyInterval:
        if self.end_slot <= self.start_slot:
            raise ValueError(f"end_slot {self.end_slot} must exceed start_slot {self.start_slot}")
        return self
