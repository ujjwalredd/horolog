"""Decompression buffers, booking links and the Linear import."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio

_tmpdir = tempfile.mkdtemp()
os.environ["HOROLOG_DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmpdir}/integrations.db"

from httpx import ASGITransport, AsyncClient

from horolog.api import app, origin
from horolog.db import init_db
from horolog.domain.events import BusyInterval
from horolog.domain.time import SLOTS_PER_HOUR
from horolog.integrations import linear
from horolog.providers import decompression_buffers
from horolog.settings import settings


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        for item in (await http.get("/api/intents")).json():
            await http.delete(f"/api/intents/{item['id']}")
        await http.put("/api/busy", json=[])
        yield http


def busy(label: str, start_slot: int, slots: int) -> BusyInterval:
    return BusyInterval(
        source_id=label, start_slot=start_slot, end_slot=start_slot + slots, label=label
    )


# ------------------------------------------------------------------ buffers


def test_buffer_trails_a_real_meeting() -> None:
    made = decompression_buffers([busy("Review", 40, 2 * SLOTS_PER_HOUR)], 15)
    assert len(made) == 1
    assert (made[0].start_slot, made[0].end_slot) == (40 + 2 * SLOTS_PER_HOUR, 40 + 8 + 1)


def test_buffer_skips_stand_ups_and_all_day_markers() -> None:
    """A 15-minute check-in needs no recovery, and a public holiday is not a
    meeting you walk out of - buffering either only burns capacity."""
    standup = busy("Stand-up", 40, 1)
    holiday = busy("Holiday", 96, 96)
    assert decompression_buffers([standup, holiday], 15) == []


def test_back_to_back_meetings_get_one_buffer_at_the_end() -> None:
    """Two touching meetings must not leave a buffer wedged between them."""
    from horolog.solver.solve import merge_busy

    first = busy("A", 40, 4)
    second = busy("B", 44, 4)
    pair = [first, second]
    merged = merge_busy(pair + decompression_buffers(pair, 15))

    assert len(merged) == 1, "the run and its buffers must collapse to one span"
    assert merged[0].start_slot == 40
    assert merged[0].end_slot == 48 + 1, "exactly one buffer, after the last meeting"


@pytest.mark.asyncio
async def test_buffers_reach_every_source_not_just_ics(client: AsyncClient) -> None:
    """The buffer used to be injected inside the ICS parser, so CalDAV and
    hand-entered events silently never got one."""
    settings.cache_clear()
    os.environ["HOROLOG_AUTO_BUFFER_ENABLED"] = "true"
    try:
        base = origin()
        await client.put(
            "/api/busy",
            json=[
                {
                    "label": "Typed in by hand",
                    "start": (base + timedelta(days=1, hours=10)).isoformat(),
                    "end": (base + timedelta(days=1, hours=11)).isoformat(),
                }
            ],
        )
        plan = (await client.get("/api/plan")).json()
        buffers = [b for b in plan["busy"] if b["source"] == "buffer"]
        assert len(buffers) == 1
        assert datetime.fromisoformat(buffers[0]["start"]).hour == 11
    finally:
        del os.environ["HOROLOG_AUTO_BUFFER_ENABLED"]
        settings.cache_clear()


# ------------------------------------------------------------------ booking


@pytest.mark.asyncio
async def test_availability_offers_only_working_hours(client: AsyncClient) -> None:
    slots = (await client.get("/api/availability?minutes=30&days=3")).json()
    assert slots, "an empty calendar must offer something"
    cfg = settings()
    for slot in slots:
        start = datetime.fromisoformat(slot["start"])
        minute_of_day = start.hour * 60 + start.minute
        assert cfg.workday_start_min <= minute_of_day < cfg.workday_end_min
        assert start > datetime.now(cfg.zone), "never offer a time that has passed"


@pytest.mark.asyncio
async def test_availability_hides_real_meetings_but_not_flexible_work(
    client: AsyncClient,
) -> None:
    """The whole point of the booking link: focus time stays bookable, because
    taking the slot moves it. A real meeting closes the slot outright."""
    base = origin()
    before = {s["start"] for s in (await client.get("/api/availability?days=3")).json()}
    assert before, "an empty calendar must offer something"

    await client.post(
        "/api/intents",
        json={"title": "Deep work", "minutes_per_period": 240, "max_chunk_minutes": 240},
    )
    plan = (await client.get("/api/plan")).json()
    assert plan["blocks"], "the fixture needs some flexible work to have been placed"

    after = {s["start"] for s in (await client.get("/api/availability?days=3")).json()}
    assert after == before, "flexible blocks must not remove a slot from the link"

    await client.put(
        "/api/busy",
        json=[
            {
                "label": "Board meeting",
                "start": (base + timedelta(days=1, hours=9)).isoformat(),
                "end": (base + timedelta(days=1, hours=17)).isoformat(),
            }
        ],
    )
    after = (await client.get("/api/availability?days=3")).json()
    blocked_day = (base + timedelta(days=1)).date()
    assert not [s for s in after if datetime.fromisoformat(s["start"]).date() == blocked_day]


@pytest.mark.asyncio
async def test_booking_pushes_flexible_work_aside(client: AsyncClient) -> None:
    await client.post(
        "/api/intents",
        json={
            "title": "Deep work",
            "minutes_per_period": 480,
            "min_chunk_minutes": 120,
            "max_chunk_minutes": 120,
        },
    )
    slot = (await client.get("/api/availability?minutes=60&days=5")).json()[0]

    booked = await client.post(
        "/api/book",
        json={"name": "Sam", "email": "sam@example.com", "start": slot["start"], "minutes": 60},
    )
    assert booked.status_code == 201

    plan = (await client.get("/api/plan")).json()
    held = next(b for b in plan["busy"] if b["source"] == "booking")
    assert held["label"] == "Booked: Sam <sam@example.com>"
    for block in plan["blocks"]:
        assert not (block["start"] < held["end"] and held["start"] < block["end"]), (
            "a booking is a real commitment - nothing may be placed over it"
        )


@pytest.mark.asyncio
async def test_double_booking_is_refused(client: AsyncClient) -> None:
    slot = (await client.get("/api/availability?minutes=30&days=5")).json()[0]
    body = {"name": "First", "start": slot["start"], "minutes": 30}
    assert (await client.post("/api/book", json=body)).status_code == 201

    clash = await client.post("/api/book", json={**body, "name": "Second"})
    assert clash.status_code == 409
    assert "taken" in clash.json()["detail"]


@pytest.mark.asyncio
async def test_an_event_before_today_does_not_brick_the_instance(client: AsyncClient) -> None:
    """A yesterday event stored a negative slot, which `BusyInterval` rejects -
    so every later read of the plan raised on the way out and the row could only
    be cleared by editing the database."""
    base = origin()
    saved = await client.put(
        "/api/busy",
        json=[
            {
                "label": "Last week",
                "start": (base - timedelta(days=7)).isoformat(),
                "end": (base - timedelta(days=6)).isoformat(),
            },
            {
                "label": "Started before midnight",
                "start": (base - timedelta(hours=2)).isoformat(),
                "end": (base + timedelta(hours=1)).isoformat(),
            },
        ],
    )
    assert saved.status_code == 200
    assert saved.json()["events"] == 1, "the fully-past event is dropped, the overlapping one kept"

    plan = await client.get("/api/plan")
    assert plan.status_code == 200
    kept = [b for b in plan.json()["busy"] if b["label"] == "Started before midnight"]
    assert kept and datetime.fromisoformat(kept[0]["start"]) == base, "clipped to the origin"


@pytest.mark.asyncio
async def test_saving_manual_events_does_not_wipe_a_booking(client: AsyncClient) -> None:
    """`PUT /api/busy` deleted every row regardless of source, so one manual
    edit erased both accepted bookings and any synced feed."""
    base = origin()
    slot = (await client.get("/api/availability?minutes=30&days=5")).json()[0]
    await client.post("/api/book", json={"name": "Sam", "start": slot["start"], "minutes": 30})

    await client.put(
        "/api/busy",
        json=[
            {
                "label": "Something typed in",
                "start": (base + timedelta(days=4, hours=9)).isoformat(),
                "end": (base + timedelta(days=4, hours=10)).isoformat(),
            }
        ],
    )
    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["busy"] if b["source"] == "booking"], "the booking must survive"


# ------------------------------------------------------------------- linear


@pytest.fixture
def linear_api(monkeypatch: pytest.MonkeyPatch) -> Callable[[object], None]:
    """Answer Linear's endpoint from a canned body.

    A factory rather than one shared client: `fetch_linear_issues` opens its own
    `AsyncClient` per call, and httpx refuses to reopen a closed one.
    """
    real = httpx.AsyncClient

    def install(body: object, status: int = 200) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "api.linear.app"
            return httpx.Response(status, json=body)

        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kw: real(**kw, transport=httpx.MockTransport(handler)),
        )

    return install


def test_linear_estimates_land_on_the_scheduling_grid() -> None:
    assert linear._minutes_for(2) == 120
    assert linear._minutes_for(None) == linear.DEFAULT_MINUTES
    assert linear._minutes_for(0) == linear.DEFAULT_MINUTES
    # 0.3 points is 18 minutes; rounding down would book 15 and call an
    # 18-minute job finished.
    assert linear._minutes_for(0.3) == 30


@pytest.mark.asyncio
async def test_linear_issues_become_schedulable_intents(
    client: AsyncClient, linear_api: Callable[[object], None]
) -> None:
    """The import used to construct `Intent` with fields that do not exist, so
    it raised a ValidationError on every issue it fetched."""
    linear_api(
        {
            "data": {
                "issues": {
                    "nodes": [
                        {
                            "id": "a",
                            "identifier": "ENG-1",
                            "title": "Ship the parser",
                            "estimate": 2,
                        },
                        {
                            "id": "b",
                            "identifier": "ENG-2",
                            "title": "Unestimated",
                            "estimate": None,
                        },
                        {"id": "c", "identifier": "ENG-3", "title": "   ", "estimate": 1},
                    ]
                }
            }
        }
    )

    synced = await client.post("/api/sync/linear", json={"api_key": "lin_api_test"})
    assert synced.status_code == 200
    assert synced.json()["issues"] == 2, "a blank title is dropped, not scheduled untitled"

    titles = {i["title"]: i for i in (await client.get("/api/intents")).json()}
    assert titles["ENG-1 Ship the parser"]["minutes_per_period"] == 120
    assert titles["ENG-2 Unestimated"]["minutes_per_period"] == 60

    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["blocks"] if b["title"].startswith("ENG-1")], (
        "an imported issue must actually get placed on the calendar"
    )


@pytest.mark.asyncio
async def test_re_syncing_linear_drops_finished_issues(
    client: AsyncClient, linear_api: Callable[[object], None]
) -> None:
    node = {"id": "a", "identifier": "ENG-1", "title": "Ship the parser", "estimate": 1}
    linear_api({"data": {"issues": {"nodes": [node]}}})
    await client.post("/api/sync/linear", json={"api_key": "k"})

    linear_api({"data": {"issues": {"nodes": []}}})
    await client.post("/api/sync/linear", json={"api_key": "k"})
    assert not [i for i in (await client.get("/api/intents")).json() if "ENG-1" in i["title"]], (
        "an issue moved out of progress must stop consuming time"
    )


@pytest.mark.asyncio
async def test_linear_graphql_errors_surface_as_a_readable_failure(
    client: AsyncClient, linear_api: Callable[[object], None]
) -> None:
    # GraphQL reports failures inside a 200 response, so raise_for_status says
    # nothing about whether the query worked.
    linear_api({"errors": [{"message": "invalid api key"}]})

    with pytest.raises(linear.LinearError, match="invalid api key"):
        await linear.fetch_linear_issues("bad")

    refused = await client.post("/api/sync/linear", json={"api_key": "bad"})
    assert refused.status_code == 502
    assert "invalid api key" in refused.json()["detail"]
