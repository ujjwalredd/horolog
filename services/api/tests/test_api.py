"""End-to-end HTTP tests against an in-process app and a temp database."""

from __future__ import annotations

import os
import tempfile
import typing
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio

_tmpdir = tempfile.mkdtemp()
os.environ["HOROLOG_DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmpdir}/test.db"

from httpx import ASGITransport, AsyncClient

from horolog.api import app, origin
from horolog.db import init_db


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        for path in ("/api/intents",):
            for item in (await http.get(path)).json():
                await http.delete(f"/api/intents/{item['id']}")
        await http.put("/api/busy", json=[])
        yield http


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/api/health")).json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_intent_schedules_it(client: AsyncClient) -> None:
    created = await client.post(
        "/api/intents",
        json={"title": "Write the design doc", "minutes_per_period": 120, "priority": 2},
    )
    assert created.status_code == 201

    plan = (await client.get("/api/plan")).json()
    mine = [b for b in plan["blocks"] if b["title"] == "Write the design doc"]
    assert mine, "a new intent must appear on the plan immediately"
    assert sum(1 for _ in mine) >= 1
    assert plan["complete"] is True
    assert plan["solve_ms"] < 500


@pytest.mark.asyncio
async def test_focus_intent_round_trips(client: AsyncClient) -> None:
    """The habits page used to mislabel every intent it created as a habit,
    even the ones its own presets called 'focus' - this pins the fix."""
    created = await client.post(
        "/api/intents",
        json={
            "title": "Deep work",
            "kind": "focus",
            "priority": 2,
            "energy": "high",
            "minutes_per_period": 600,
            "period_days": 7,
            "min_chunk_minutes": 120,
            "max_chunk_minutes": 120,
        },
    )
    assert created.status_code == 201

    intents = (await client.get("/api/intents")).json()
    mine = next(i for i in intents if i["title"] == "Deep work")
    assert mine["kind"] == "focus"
    assert mine["energy"] == "high"


@pytest.mark.asyncio
async def test_busy_events_push_work_aside(client: AsyncClient) -> None:
    await client.post(
        "/api/intents",
        json={
            "title": "Deep work",
            "minutes_per_period": 120,
            "min_chunk_minutes": 120,
            "max_chunk_minutes": 120,
        },
    )
    before = (await client.get("/api/plan")).json()
    first = next(b for b in before["blocks"] if b["title"] == "Deep work")

    base = origin()
    blocked = [
        {
            "label": "All-hands",
            "start": (base + timedelta(days=d, hours=9)).isoformat(),
            "end": (base + timedelta(days=d, hours=17)).isoformat(),
        }
        for d in range(3)
    ]
    await client.put("/api/busy", json=blocked)

    after = (await client.get("/api/plan")).json()
    moved = next(b for b in after["blocks"] if b["title"] == "Deep work")
    assert moved["start"] != first["start"], "work must move off a newly blocked day"
    for block in after["blocks"]:
        assert not (block["start"] < blocked[0]["end"] and blocked[0]["start"] < block["end"])


@pytest.mark.asyncio
async def test_replanning_an_unchanged_calendar_changes_nothing(client: AsyncClient) -> None:
    for i in range(4):
        await client.post("/api/intents", json={"title": f"task {i}", "minutes_per_period": 60})

    first = (await client.post("/api/plan/solve")).json()
    again = (await client.post("/api/plan/solve")).json()

    def key(plan: dict[str, typing.Any]) -> dict[str, str]:
        return {
            f"{b['intent_id']}:{b['occurrence']}:{b['chunk']}": b["start"] for b in plan["blocks"]
        }

    assert key(first) == key(again), "a no-op re-solve must not move a single block"


@pytest.mark.asyncio
async def test_impossible_intent_is_rejected_with_a_reason(client: AsyncClient) -> None:
    response = await client.post(
        "/api/intents",
        json={
            "title": "impossible",
            "minutes_per_period": 240,
            "min_chunk_minutes": 240,
            "window_start_min": 600,
            "window_end_min": 630,
        },
    )
    assert response.status_code == 422
    assert "min_chunk" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oversubscribed_calendar_reports_shortfall(client: AsyncClient) -> None:
    for i in range(40):
        await client.post(
            "/api/intents",
            json={"title": f"big {i}", "minutes_per_period": 480, "max_chunk_minutes": 480},
        )
    plan = (await client.get("/api/plan")).json()
    assert plan["complete"] is False
    assert plan["unmet"], "unplaceable demand must be reported, not dropped"
    assert plan["unmet"][0]["shortfall_minutes"] > 0


@pytest.mark.asyncio
async def test_accepts_floating_local_times(client: AsyncClient) -> None:
    """ICS files and browser `toISOString()` both hand over datetimes with no
    offset. Those must be read in the configured zone, not 500."""
    base = origin().replace(tzinfo=None)
    response = await client.put(
        "/api/busy",
        json=[
            {
                "label": "Naive meeting",
                "start": (base + timedelta(days=1, hours=10)).isoformat(),
                "end": (base + timedelta(days=1, hours=11)).isoformat(),
            }
        ],
    )
    assert response.status_code == 200
    plan = (await client.get("/api/plan")).json()
    assert plan["busy"][0]["label"] == "Naive meeting"
    # It comes back offset-aware, whatever the host's zone happens to be — the
    # point is that it was interpreted, not that it was interpreted as UTC.
    assert datetime.fromisoformat(plan["busy"][0]["start"]).tzinfo is not None


@pytest.mark.asyncio
async def test_smart_meeting_lands_in_shared_availability(client: AsyncClient) -> None:
    """A Smart Meeting must dodge the other attendees' calendars — while
    leaving those same hours free for the user's own solo work."""
    base = origin()
    busy_for_them = [
        {
            "start": (base + timedelta(days=d, hours=9)).isoformat(),
            "end": (base + timedelta(days=d, hours=15)).isoformat(),
            "attendee": "sam@example.com",
        }
        for d in range(7)
    ]
    await client.post(
        "/api/intents",
        json={
            "title": "Weekly sync",
            "kind": "meeting",
            "priority": 2,
            "minutes_per_period": 60,
            "min_chunk_minutes": 60,
            "max_chunk_minutes": 60,
            "attendee_busy": busy_for_them,
        },
    )
    await client.post(
        "/api/intents",
        json={
            "title": "Solo focus",
            "kind": "focus",
            "minutes_per_period": 120,
            "min_chunk_minutes": 120,
            "max_chunk_minutes": 120,
        },
    )
    plan = (await client.get("/api/plan")).json()

    meeting = next(b for b in plan["blocks"] if b["title"] == "Weekly sync")
    hour = datetime.fromisoformat(meeting["start"]).hour
    assert hour >= 15, "the meeting must avoid every attendee's blocked hours"

    focus = next(b for b in plan["blocks"] if b["title"] == "Solo focus")
    assert datetime.fromisoformat(focus["start"]).hour < 15, (
        "an attendee's calendar must not block the user's own solo work"
    )


def _mock_llm(
    monkeypatch: pytest.MonkeyPatch, handler: typing.Callable[[httpx.Request], httpx.Response]
) -> None:
    """Route the app's own outbound `httpx.AsyncClient` calls to `handler`,
    so a captured request never actually leaves the process."""
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler))
    )


@pytest.mark.asyncio
async def test_capture_when_the_model_is_unreachable_returns_503_not_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A connection failure to the LLM backend (wrong HOROLOG_LLM_BASE_URL,
    the model server not running yet) is the operator's problem, not a crash —
    the endpoint must say so with a 503, never a bare 500."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _mock_llm(monkeypatch, handler)
    response = await client.post("/api/capture", json={"text": "gym 3x a week"})
    assert response.status_code == 503
    assert "could not reach" in response.json()["detail"]


@pytest.mark.asyncio
async def test_capture_when_the_model_returns_404_surfaces_the_body(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ollama's 404 body says 'model not found, try pulling it first' — that
    text is the one actionable thing here and must survive into the
    response, not get discarded by a generic status-code message."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model 'qwen3:8b' not found, try pulling it first")

    _mock_llm(monkeypatch, handler)
    response = await client.post("/api/capture", json={"text": "gym 3x a week"})
    assert response.status_code == 503
    assert "not found, try pulling it first" in response.json()["detail"]


@pytest.mark.asyncio
async def test_capture_when_the_model_returns_an_unexpected_shape_returns_503_not_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 200 with no `choices` key — e.g. a reverse proxy's own error page,
    or a server that isn't actually OpenAI-chat-compatible — must not crash
    the endpoint with an unhandled KeyError."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "not the shape you expected"})

    _mock_llm(monkeypatch, handler)
    response = await client.post("/api/capture", json={"text": "gym 3x a week"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_capture_with_anthropic_selected_but_sdk_missing_returns_503_not_500(
    client: AsyncClient,
) -> None:
    """`anthropic` is an optional extra, not in the documented dev install
    (`.[dev]`) — only the Docker image has it. Picking "Anthropic" in the UI
    without it installed must surface the friendly install message, not a
    bare 500. No mocking needed: the package genuinely isn't in this venv."""
    response = await client.post(
        "/api/capture",
        json={"text": "gym 3x a week", "provider": "anthropic", "model": "claude-opus-5"},
    )
    assert response.status_code == 503
    assert "horolog[anthropic]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sync_ics_when_the_feed_is_unreachable_returns_502_not_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dead or mistyped .ics URL is the user's mistake to fix, not a server
    crash — must map to 502 with the reason included."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name or service not known")

    _mock_llm(monkeypatch, handler)
    response = await client.post(
        "/api/sync/ics", json={"url": "https://example.invalid/calendar.ics"}
    )
    assert response.status_code == 502


# --------------------------------------------------------------- task lifecycle


@pytest.mark.asyncio
async def test_completing_a_task_frees_its_capacity_on_the_next_solve(
    client: AsyncClient,
) -> None:
    created = (
        await client.post(
            "/api/intents", json={"title": "Ship the thing", "minutes_per_period": 60}
        )
    ).json()

    plan = (await client.get("/api/plan")).json()
    assert any(b["intent_id"] == created["id"] for b in plan["blocks"])

    done = await client.post(f"/api/intents/{created['id']}/complete")
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None

    plan = (await client.get("/api/plan")).json()
    assert not any(b["intent_id"] == created["id"] for b in plan["blocks"]), (
        "a completed task must not keep occupying a slot"
    )

    intents = (await client.get("/api/intents")).json()
    mine = next(i for i in intents if i["id"] == created["id"])
    assert mine["completed_at"] is not None, "the row is kept, not deleted"


@pytest.mark.asyncio
async def test_uncompleting_a_task_restores_it_to_the_plan(client: AsyncClient) -> None:
    created = (
        await client.post("/api/intents", json={"title": "Redo it", "minutes_per_period": 60})
    ).json()
    await client.post(f"/api/intents/{created['id']}/complete")

    undone = await client.delete(f"/api/intents/{created['id']}/complete")
    assert undone.status_code == 200
    assert undone.json()["completed_at"] is None

    plan = (await client.get("/api/plan")).json()
    assert any(b["intent_id"] == created["id"] for b in plan["blocks"])


@pytest.mark.asyncio
async def test_completing_a_recurring_habit_is_rejected(client: AsyncClient) -> None:
    """Completion is scoped to one-shot tasks — a habit needs per-occurrence
    state that does not exist yet, so it must fail loudly, not silently no-op
    or complete the whole recurring series."""
    created = (
        await client.post(
            "/api/intents",
            json={
                "title": "Gym",
                "kind": "habit",
                "minutes_per_period": 180,
                "period_days": 7,
                "min_chunk_minutes": 60,
                "max_chunk_minutes": 60,
            },
        )
    ).json()
    response = await client.post(f"/api/intents/{created['id']}/complete")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_completing_an_unknown_intent_is_404(client: AsyncClient) -> None:
    response = await client.post("/api/intents/does-not-exist/complete")
    assert response.status_code == 404


def _no_overlaps(blocks: list[dict[str, typing.Any]], intent_id: str) -> bool:
    mine = sorted(
        (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
        for b in blocks
        if b["intent_id"] == intent_id
    )
    return all(mine[i][1] <= mine[i + 1][0] for i in range(len(mine) - 1))


@pytest.mark.asyncio
async def test_editing_an_intent_keeps_its_id_and_stays_stable_when_unchanged(
    client: AsyncClient,
) -> None:
    created = (
        await client.post(
            "/api/intents", json={"title": "Original", "minutes_per_period": 60, "priority": 3}
        )
    ).json()
    before = (await client.get("/api/plan")).json()
    was = next(b for b in before["blocks"] if b["intent_id"] == created["id"])

    edited = await client.put(
        f"/api/intents/{created['id']}",
        json={"title": "Original", "minutes_per_period": 60, "priority": 1},
    )
    assert edited.status_code == 200
    assert edited.json()["id"] == created["id"]

    after = (await client.get("/api/plan")).json()
    now = next(b for b in after["blocks"] if b["intent_id"] == created["id"])
    assert now["start"] == was["start"], "an edit that doesn't touch duration must not move it"
    assert now["priority"] == 1


@pytest.mark.asyncio
async def test_editing_an_intent_larger_does_not_overlap_or_orphan(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/intents",
            json={
                "title": "Grows",
                "minutes_per_period": 120,
                "min_chunk_minutes": 30,
                "max_chunk_minutes": 120,
            },
        )
    ).json()

    edited = await client.put(
        f"/api/intents/{created['id']}",
        json={
            "title": "Grows",
            "minutes_per_period": 180,
            "min_chunk_minutes": 30,
            "max_chunk_minutes": 120,
        },
    )
    assert edited.status_code == 200

    plan = (await client.get("/api/plan")).json()
    assert _no_overlaps(plan["blocks"], created["id"])
    placed = sum(
        (datetime.fromisoformat(b["end"]) - datetime.fromisoformat(b["start"])).total_seconds()
        for b in plan["blocks"]
        if b["intent_id"] == created["id"]
    )
    assert placed == 180 * 60


@pytest.mark.asyncio
async def test_editing_an_intent_smaller_does_not_overlap_or_orphan(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/intents",
            json={
                "title": "Shrinks",
                "minutes_per_period": 180,
                "min_chunk_minutes": 30,
                "max_chunk_minutes": 120,
            },
        )
    ).json()

    edited = await client.put(
        f"/api/intents/{created['id']}",
        json={
            "title": "Shrinks",
            "minutes_per_period": 60,
            "min_chunk_minutes": 30,
            "max_chunk_minutes": 120,
        },
    )
    assert edited.status_code == 200

    plan = (await client.get("/api/plan")).json()
    assert _no_overlaps(plan["blocks"], created["id"])
    placed = sum(
        (datetime.fromisoformat(b["end"]) - datetime.fromisoformat(b["start"])).total_seconds()
        for b in plan["blocks"]
        if b["intent_id"] == created["id"]
    )
    assert placed == 60 * 60


@pytest.mark.asyncio
async def test_editing_an_unknown_intent_is_404(client: AsyncClient) -> None:
    response = await client.put(
        "/api/intents/does-not-exist", json={"title": "x", "minutes_per_period": 30}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_editing_an_intent_rejects_the_same_invalid_shapes_as_creating_one(
    client: AsyncClient,
) -> None:
    created = (
        await client.post("/api/intents", json={"title": "Fine", "minutes_per_period": 60})
    ).json()
    response = await client.put(
        f"/api/intents/{created['id']}",
        json={
            "title": "Fine",
            "minutes_per_period": 60,
            "min_chunk_minutes": 90,
            "max_chunk_minutes": 30,
        },
    )
    assert response.status_code == 422
