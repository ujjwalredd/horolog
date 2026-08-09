"""End-to-end HTTP tests against an in-process app and a temp database."""

from __future__ import annotations

import os
import tempfile
import typing
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

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
