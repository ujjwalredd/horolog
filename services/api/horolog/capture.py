"""Natural language -> a validated scheduling intent.

The one place a language model touches this product. It fills in a form; it
never picks a time. Whatever it returns is a *request* for time that the placer
then satisfies or reports as unmet against the real calendar — so a bad
extraction produces a wrong-looking task, never a phantom event.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field, model_validator

from horolog.domain.intent import EnergyLevel, IntentKind, Priority
from horolog.llm import Provider, extract

SYSTEM = """\
You convert a person's description of work into one scheduling request.

Rules:
- minutes_per_period is the TOTAL time needed, not the length of one sitting.
- period_days: null for one-off work. 7 for anything described as weekly,
  "every week", or a number of times per week. 1 for daily.
- min_chunk_minutes / max_chunk_minutes bound a single sitting. Set them equal
  when the activity cannot be split (a gym session, a class, a meeting).
- Deep or focused work wants min_chunk_minutes of at least 60.
- max_per_day: 1 when the person implies it happens at most once a day
  ("three times a week", "every morning"). Otherwise null.
- window_start_min / window_end_min are minutes from midnight, for phrases like
  "in the mornings" (540-720) or "between 2 and 6" (840-1080). Null if unstated.
- due_in_days counts from today. Null when no deadline is mentioned.
- Priority: 1 critical, 2 high, 3 normal, 4 low. Default 3 unless urgency,
  importance, or "whenever" language says otherwise.
- energy: "high" only when the text itself implies demanding/creative work or a
  preference for peak alertness ("when I'm sharpest", "best focus", "deep work").
  Otherwise null - do not guess.

Infer only what the text supports. Use null rather than inventing a constraint.\
"""


class IntentDraft(BaseModel):
    """What the model is allowed to say.

    Deliberately expressed in the units a person speaks in — minutes, days,
    times per week — rather than the engine's 15-minute slots. Asking a model
    to do the arithmetic invites errors that grammar constraints cannot catch,
    and the conversion is one line of Python.
    """

    title: str = Field(min_length=1, max_length=200)
    kind: IntentKind
    priority: Priority
    energy: EnergyLevel | None
    minutes_per_period: int
    period_days: int | None
    min_chunk_minutes: int
    max_chunk_minutes: int
    max_per_day: int | None
    window_start_min: int | None
    window_end_min: int | None
    due_in_days: int | None

    @model_validator(mode="after")
    def _sane(self) -> IntentDraft:
        # These are the checks constrained decoding cannot make: the grammar
        # guarantees an integer sits in `min_chunk_minutes`, not that it is
        # smaller than the maximum. A failure here triggers the repair round.
        if self.minutes_per_period <= 0:
            raise ValueError("minutes_per_period must be positive")
        if self.min_chunk_minutes <= 0 or self.max_chunk_minutes <= 0:
            raise ValueError("chunk minutes must be positive")
        if self.max_chunk_minutes < self.min_chunk_minutes:
            raise ValueError("max_chunk_minutes must be >= min_chunk_minutes")
        if self.minutes_per_period < self.min_chunk_minutes:
            raise ValueError(
                f"minutes_per_period ({self.minutes_per_period}) is less than one "
                f"chunk ({self.min_chunk_minutes}); reduce min_chunk_minutes"
            )
        if (self.window_start_min is None) != (self.window_end_min is None):
            raise ValueError("window_start_min and window_end_min must both be set or both null")
        if self.window_start_min is not None and self.window_end_min is not None:
            if not 0 <= self.window_start_min < self.window_end_min <= 1440:
                raise ValueError("window must satisfy 0 <= start < end <= 1440")
            if self.window_end_min - self.window_start_min < self.min_chunk_minutes:
                raise ValueError(
                    f"window is {self.window_end_min - self.window_start_min}min but a chunk "
                    f"needs {self.min_chunk_minutes}min; widen the window or shorten the chunk"
                )
        if self.due_in_days is not None and self.due_in_days < 0:
            raise ValueError("due_in_days cannot be negative")
        return self


def to_payload(draft: IntentDraft, now: datetime) -> dict[str, object]:
    """Convert a draft into the body `POST /api/intents` accepts."""
    step = 15

    def up(minutes: int) -> int:
        """Snap up to the engine's 15-minute grid.

        Up, not nearest: a 20-minute task rounded down would be scheduled for
        15 minutes and then reported complete.
        """
        return max(step, -(-minutes // step) * step)

    payload: dict[str, object] = {
        "title": draft.title,
        "kind": draft.kind.value,
        "priority": int(draft.priority),
        "energy": draft.energy.value if draft.energy is not None else None,
        "minutes_per_period": up(draft.minutes_per_period),
        "period_days": draft.period_days,
        "min_chunk_minutes": up(draft.min_chunk_minutes),
        "max_chunk_minutes": up(draft.max_chunk_minutes),
        "max_per_day": draft.max_per_day,
        "window_start_min": draft.window_start_min,
        "window_end_min": draft.window_end_min,
    }
    if draft.due_in_days is not None:
        payload["due"] = (now + timedelta(days=draft.due_in_days)).isoformat()
    return payload


async def capture(text: str, provider: Provider | None = None) -> IntentDraft:
    return await extract(IntentDraft, SYSTEM, text, provider=provider)
