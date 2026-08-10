"""Natural-language capture, with a scripted provider instead of a live model.

The point of these tests is the layer *around* the model: schema tightening,
semantic validation the grammar cannot enforce, the repair round, and the
conversion into engine units. None of that should need a GPU to verify.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from horolog.capture import IntentDraft, capture, to_payload
from horolog.domain.intent import IntentKind, Priority
from horolog.llm import ExtractionFailed, strict_schema

NOW = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


class ScriptedProvider:
    """Returns canned payloads in order, recording the prompts it was given."""

    def __init__(self, *payloads: dict[str, Any]) -> None:
        self._payloads = list(payloads)
        self.prompts: list[str] = []
        self.schemas: list[dict[str, Any]] = []

    async def complete(self, system: str, user: str, schema: dict[str, Any], name: str) -> str:
        self.prompts.append(user)
        self.schemas.append(schema)
        return json.dumps(self._payloads.pop(0))


def draft(**overrides: Any) -> dict[str, Any]:
    base = {
        "title": "Write the design doc",
        "kind": "task",
        "priority": 2,
        "energy": None,
        "minutes_per_period": 180,
        "period_days": None,
        "min_chunk_minutes": 60,
        "max_chunk_minutes": 120,
        "max_per_day": None,
        "window_start_min": None,
        "window_end_min": None,
        "due_in_days": 3,
    }
    return {**base, **overrides}


def test_strict_schema_is_acceptable_to_constrained_decoders() -> None:
    """Both providers reject open schemas; OpenAI additionally requires every
    property listed in `required`, with optionality expressed as a null union."""
    schema = strict_schema(IntentDraft)

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["due_in_days"]["anyOf"] == [
        {"type": "integer"},
        {"type": "null"},
    ]
    # Bounds neither engine supports must not survive, or the schema is refused.
    assert "maxLength" not in json.dumps(schema)
    assert "minimum" not in json.dumps(schema)


@pytest.mark.asyncio
async def test_captures_a_plain_request() -> None:
    provider = ScriptedProvider(draft())
    result = await capture("I need to write the design doc, about 3 hours, by Thursday", provider)

    assert result.title == "Write the design doc"
    assert result.kind is IntentKind.TASK
    assert result.priority is Priority.P2
    assert len(provider.prompts) == 1, "a valid first answer must not trigger a repair round"


@pytest.mark.asyncio
async def test_repairs_a_semantically_invalid_answer() -> None:
    """Grammar constraints guarantee an integer, not a *sensible* one.

    A chunk larger than the total is well-formed JSON and structurally valid;
    only the model validator catches it, and the repair round is what turns
    that into a usable result instead of a failure.
    """
    provider = ScriptedProvider(
        draft(minutes_per_period=30, min_chunk_minutes=60),  # impossible
        draft(minutes_per_period=30, min_chunk_minutes=30, max_chunk_minutes=30),
    )
    result = await capture("quick 30 minute call", provider)

    assert result.minutes_per_period == 30
    assert len(provider.prompts) == 2
    assert "rejected" in provider.prompts[1], "the repair prompt must carry the reason"


@pytest.mark.asyncio
async def test_gives_up_loudly_after_one_repair() -> None:
    """Two failures surface as an error so the UI can fall back to a form,
    rather than looping against a model that cannot do the task."""
    bad = draft(minutes_per_period=30, min_chunk_minutes=60)
    provider = ScriptedProvider(bad, bad)

    with pytest.raises(ExtractionFailed, match="repair round"):
        await capture("nonsense", provider)


@pytest.mark.asyncio
async def test_rejects_a_window_too_short_for_its_chunk() -> None:
    """A 30-minute window cannot hold a 60-minute block. Caught here rather
    than downstream, where it would silently become permanent unmet demand."""
    provider = ScriptedProvider(
        draft(window_start_min=600, window_end_min=630, min_chunk_minutes=60),
        draft(window_start_min=600, window_end_min=720, min_chunk_minutes=60),
    )
    result = await capture("an hour of focus, late morning", provider)

    assert result.window_end_min == 720
    assert "widen the window" in provider.prompts[1]


@pytest.mark.asyncio
async def test_rejects_a_half_specified_window() -> None:
    provider = ScriptedProvider(
        draft(window_start_min=540, window_end_min=None),
        draft(window_start_min=540, window_end_min=720),
    )
    await capture("mornings", provider)
    assert "both be set or both null" in provider.prompts[1]


def test_payload_rounds_durations_up_to_the_grid() -> None:
    """Rounding down would schedule 15 minutes for a 20-minute task and then
    report it finished."""
    payload = to_payload(
        IntentDraft.model_validate(
            draft(minutes_per_period=20, min_chunk_minutes=20, max_chunk_minutes=20)
        ),
        NOW,
    )

    assert payload["minutes_per_period"] == 30
    assert payload["min_chunk_minutes"] == 30


def test_payload_converts_a_relative_deadline_to_an_absolute_one() -> None:
    payload = to_payload(IntentDraft.model_validate(draft(due_in_days=3)), NOW)
    assert str(payload["due"]).startswith("2026-03-05")


def test_payload_omits_due_when_there_is_no_deadline() -> None:
    payload = to_payload(IntentDraft.model_validate(draft(due_in_days=None)), NOW)
    assert "due" not in payload


@pytest.mark.asyncio
async def test_habit_shape_survives_the_round_trip() -> None:
    provider = ScriptedProvider(
        draft(
            title="Gym",
            kind="habit",
            priority=3,
            minutes_per_period=180,
            period_days=7,
            min_chunk_minutes=60,
            max_chunk_minutes=60,
            max_per_day=1,
            window_start_min=600,
            window_end_min=960,
            due_in_days=None,
        )
    )
    result = await capture("gym three times a week for an hour, between 10 and 4", provider)
    payload = to_payload(result, NOW)

    assert payload["period_days"] == 7
    assert payload["max_per_day"] == 1
    assert payload["min_chunk_minutes"] == payload["max_chunk_minutes"] == 60
    assert (payload["window_start_min"], payload["window_end_min"]) == (600, 960)
