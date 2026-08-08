"""HTTP surface.

Slots stop at this boundary: everything crossing the wire is an ISO datetime.
The UI never learns that the engine thinks in 15-minute integers.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from horolog.analytics import Analytics, analyse
from horolog.capture import capture, to_payload
from horolog.db import (
    BusyRow,
    IntentRow,
    init_db,
    load_intents,
    load_previous_plan,
    save_plan,
    session,
)
from horolog.domain.events import BusyInterval
from horolog.domain.intent import DailyWindow, Intent, IntentKind, Priority
from horolog.domain.plan import Plan
from horolog.domain.time import SLOTS_PER_DAY, from_slot, minutes_to_slots, to_slot
from horolog.llm import ExtractionFailed
from horolog.providers import (
    CalDAVProvider,
    CalendarProvider,
    ICSProvider,
    SyncError,
    to_ics,
)
from horolog.settings import settings
from horolog.solver.solve import solve

# --------------------------------------------------------------------------
# Time origin
# --------------------------------------------------------------------------


def origin() -> datetime:
    """Midnight today in the configured zone.

    Recomputed per request rather than pinned at boot, so a process that stays
    up across midnight does not keep scheduling into yesterday.
    """
    now = datetime.now(settings().zone)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def horizon_slots() -> int:
    return settings().horizon_days * SLOTS_PER_DAY


def _localise(value: datetime | None) -> datetime | None:
    """Attach the configured zone to a naive datetime.

    ICS files and plenty of calendar clients emit "floating" local times with no
    offset, and a browser's `toISOString()` drops the zone too. The engine
    requires aware datetimes, so without normalising here every such input
    reaches `to_slot` and raises — a 500 for input that is entirely ordinary.

    Applied as a field validator on every wire model rather than at each call
    site, so a new datetime field cannot reintroduce the bug by omission.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=settings().zone)


LocalDateTime = Annotated[datetime, AfterValidator(_localise)]


# --------------------------------------------------------------------------
# Wire contracts
# --------------------------------------------------------------------------


class IntentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: IntentKind = IntentKind.TASK
    priority: Priority = Priority.P3
    minutes_per_period: int = Field(gt=0)
    period_days: int | None = Field(default=None, gt=0)
    min_chunk_minutes: int = Field(default=30, gt=0)
    max_chunk_minutes: int = Field(default=120, gt=0)
    max_per_day: int | None = Field(default=None, gt=0)
    window_start_min: int | None = None
    window_end_min: int | None = None
    due: LocalDateTime | None = None
    earliest: LocalDateTime | None = None
    preferred_start_min: int | None = None

    attendee_busy: list[AttendeeBusy] = Field(default_factory=list)
    """Other attendees' commitments, for a Smart Meeting.

    Constrains this intent only. Deliberately not merged into the shared busy
    mirror: a colleague being booked at 2pm must stop *this meeting* landing at
    2pm without blanking 2pm out for your own focus time."""

    def to_domain(self, ident: str, base: datetime) -> Intent:
        cfg = settings()
        start = (
            self.window_start_min if self.window_start_min is not None else cfg.workday_start_min
        )
        end = self.window_end_min if self.window_end_min is not None else cfg.workday_end_min
        return Intent(
            id=ident,
            kind=self.kind,
            title=self.title,
            priority=self.priority,
            minutes_per_period=self.minutes_per_period,
            period_days=self.period_days,
            min_chunk_minutes=self.min_chunk_minutes,
            max_chunk_minutes=self.max_chunk_minutes,
            max_per_day=self.max_per_day,
            daily_windows=[DailyWindow(start_min=start, end_min=end)],
            earliest_slot=to_slot(self.earliest, base) if self.earliest else None,
            due_slot=to_slot(self.due, base) if self.due else None,
            preferred_start_min=self.preferred_start_min,
            blocked_slots=[
                (to_slot(a.start, base), to_slot(a.end, base))
                for a in self.attendee_busy
                if to_slot(a.end, base) > to_slot(a.start, base)
            ],
        )


class AttendeeBusy(BaseModel):
    """One span in which some other attendee is unavailable."""

    start: LocalDateTime
    end: LocalDateTime
    attendee: str = ""


class BusyIn(BaseModel):
    label: str = ""
    start: LocalDateTime
    end: LocalDateTime
    source: str = "manual"


class BlockOut(BaseModel):
    intent_id: str
    title: str
    kind: IntentKind
    priority: Priority
    occurrence: int
    chunk: int
    start: datetime
    end: datetime
    moved_from: datetime | None = None


class UnmetOut(BaseModel):
    intent_id: str
    title: str
    priority: Priority
    shortfall_minutes: int


class PlanOut(BaseModel):
    blocks: list[BlockOut]
    unmet: list[UnmetOut]
    busy: list[BusyIn]
    solve_ms: float
    complete: bool
    generated_at: datetime
    origin: datetime
    horizon_days: int


# --------------------------------------------------------------------------
# Change stream
# --------------------------------------------------------------------------


class Broadcast:
    """Fan-out to connected SSE clients.

    ponytail: in-process only. Multiple API workers each hold their own
    subscriber set, so a change on worker A never reaches a client attached to
    worker B. Move to Postgres LISTEN/NOTIFY when running more than one process.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[str]]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=16)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, event: str) -> None:
        for queue in list(self._subscribers):
            # A client too slow to keep up is dropped from this message rather
            # than allowed to block the request that produced it.
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)


bus = Broadcast()


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(title="Horolog", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/intents")
async def list_intents(db: AsyncSession = Depends(session)) -> list[dict[str, Any]]:
    rows = (await db.execute(select(IntentRow))).scalars().all()
    return [row.payload for row in rows]


@app.post("/api/intents", status_code=201)
async def create_intent(body: IntentIn, db: AsyncSession = Depends(session)) -> dict[str, Any]:
    ident = uuid.uuid4().hex[:12]
    try:
        intent = body.to_domain(ident, origin())
    except ValueError as exc:
        # Domain validation is the real gate; surface its message rather than a
        # generic 500, because it explains exactly why the intent is impossible.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(IntentRow(id=ident, payload=intent.model_dump(mode="json")))
    await db.commit()
    await _replan(db)
    return intent.model_dump(mode="json")


class CaptureIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@app.post("/api/capture", status_code=201)
async def capture_intent(body: CaptureIn, db: AsyncSession = Depends(session)) -> dict[str, Any]:
    """Natural language in, a scheduled intent out.

    The model's output is a proposal: it is schema-constrained at decode time,
    Pydantic-validated here, and then re-validated by the domain model through
    the ordinary create path. It never reaches a calendar except by way of the
    placer, so the worst a bad extraction can do is create a wrong-looking
    intent the user can delete.
    """
    try:
        draft = await capture(body.text)
    except ExtractionFailed as exc:
        # Explicitly not a 500: the request was fine, the model could not read
        # it. The UI falls back to the manual form on this status.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"language model unreachable: {exc}") from exc

    payload = to_payload(draft, origin())
    created = await create_intent(IntentIn.model_validate(payload), db)
    return {"intent": created, "understood": draft.model_dump(mode="json")}


@app.delete("/api/intents/{intent_id}")
async def delete_intent(intent_id: str, db: AsyncSession = Depends(session)) -> Response:
    row = await db.get(IntentRow, intent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no intent {intent_id!r}")
    await db.delete(row)
    await db.commit()
    await _replan(db)
    return Response(status_code=204)


@app.put("/api/busy", status_code=200)
async def replace_busy(body: list[BusyIn], db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Replace the mirrored calendar wholesale.

    Stands in for the provider sync layer: whatever CalDAV or Google reports
    becomes the set of immovable events. Replacing rather than merging keeps the
    mirror an exact reflection, so a deleted meeting actually frees its slot.
    """
    base = origin()
    await db.execute(delete(BusyRow))
    for event in body:
        if event.end <= event.start:
            raise HTTPException(status_code=422, detail=f"{event.label!r} ends before it starts")
        db.add(
            BusyRow(
                id=uuid.uuid4().hex[:16],
                source=event.source,
                label=event.label,
                start_slot=to_slot(event.start, base),
                end_slot=to_slot(event.end, base),
            )
        )
    await db.commit()
    plan = await _replan(db)
    return {"events": len(body), "blocks": len(plan.blocks)}


@app.get("/api/plan")
async def get_plan(db: AsyncSession = Depends(session)) -> PlanOut:
    plan = await load_previous_plan(db)
    if plan is None:
        plan = await _replan(db)
    return await _render(db, plan)


@app.post("/api/plan/solve")
async def resolve(db: AsyncSession = Depends(session)) -> PlanOut:
    return await _render(db, await _replan(db))


@app.get("/api/analytics")
async def analytics(db: AsyncSession = Depends(session)) -> Analytics:
    """How the plan actually spends the week."""
    cfg = settings()
    plan = await load_previous_plan(db) or await _replan(db)
    rows = (await db.execute(select(BusyRow))).scalars().all()
    return analyse(
        plan,
        await load_intents(db),
        [
            BusyInterval(
                source_id=r.id, start_slot=r.start_slot, end_slot=r.end_slot, label=r.label
            )
            for r in rows
        ],
        horizon_days=cfg.horizon_days,
        workday_start_min=cfg.workday_start_min,
        workday_end_min=cfg.workday_end_min,
    )


class IcsSyncIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


@app.post("/api/sync/ics")
async def sync_ics(body: IcsSyncIn, db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Mirror a published .ics feed.

    The zero-config path onto Google and Outlook: both publish a private iCal
    address, so this needs no OAuth app and no publicly reachable callback.
    """
    cfg = settings()
    provider = ICSProvider(body.url, cfg.zone)
    return await _mirror(db, provider, "ics")


class CalDavSyncIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    username: str = ""
    password: str = ""


@app.post("/api/sync/caldav")
async def sync_caldav(body: CalDavSyncIn, db: AsyncSession = Depends(session)) -> dict[str, int]:
    cfg = settings()
    provider = CalDAVProvider(body.url, body.username, body.password, cfg.zone)
    return await _mirror(db, provider, "caldav")


@app.get("/api/plan.ics")
async def export_ics(db: AsyncSession = Depends(session)) -> Response:
    """Subscribe to the plan from any calendar app, read-only.

    The safest possible write path: a subscribing client can render the plan but
    can never corrupt the calendar it was derived from.
    """
    base = origin()
    plan = await load_previous_plan(db) or await _replan(db)
    titles = {i.id: i.title for i in await load_intents(db)}
    body = to_ics(
        [
            (
                titles.get(b.intent_id, b.intent_id),
                from_slot(b.start_slot, base),
                from_slot(b.end_slot, base),
            )
            for b in plan.blocks
        ]
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="horolog.ics"'},
    )


@app.get("/api/stream")
async def stream() -> EventSourceResponse:
    async def events() -> AsyncIterator[dict[str, str]]:
        async with bus.subscribe() as queue:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20)
                except TimeoutError:
                    # Proxies drop idle connections; a comment frame keeps the
                    # stream alive without inventing a fake domain event.
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield {"event": "plan", "data": payload}

    return EventSourceResponse(events())


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------


async def _mirror(db: AsyncSession, provider: CalendarProvider, source: str) -> dict[str, int]:
    """Replace the mirror for one source, then re-plan.

    Replace rather than merge: the mirror is meant to be an exact reflection of
    the upstream calendar, so a meeting deleted there has to free its slot here.
    Scoped to `source` so syncing an ICS feed does not wipe CalDAV events.
    """
    try:
        events = await provider.fetch(origin(), settings().horizon_days)
    except SyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await db.execute(delete(BusyRow).where(BusyRow.source == source))
    for event in events:
        db.add(
            BusyRow(
                id=f"{source}:{uuid.uuid4().hex[:12]}",
                source=source,
                label=event.label,
                start_slot=event.start_slot,
                end_slot=event.end_slot,
            )
        )
    await db.commit()
    plan = await _replan(db)
    return {"events": len(events), "blocks": len(plan.blocks)}


async def _replan(db: AsyncSession) -> Plan:
    intents = await load_intents(db)
    rows = (await db.execute(select(BusyRow))).scalars().all()
    busy = [
        BusyInterval(
            source_id=row.id, start_slot=row.start_slot, end_slot=row.end_slot, label=row.label
        )
        for row in rows
    ]
    plan = solve(intents, busy, horizon_slots(), previous=await load_previous_plan(db))
    await save_plan(db, plan)
    bus.publish(json.dumps({"blocks": len(plan.blocks), "solve_ms": round(plan.solve_ms, 2)}))
    return plan


async def _render(db: AsyncSession, plan: Plan) -> PlanOut:
    base = origin()
    titles = {i.id: i for i in await load_intents(db)}
    rows = (await db.execute(select(BusyRow))).scalars().all()
    return PlanOut(
        blocks=[
            BlockOut(
                intent_id=b.intent_id,
                title=titles[b.intent_id].title if b.intent_id in titles else b.intent_id,
                kind=titles[b.intent_id].kind if b.intent_id in titles else IntentKind.TASK,
                priority=b.priority,
                occurrence=b.occurrence,
                chunk=b.chunk,
                start=from_slot(b.start_slot, base),
                end=from_slot(b.end_slot, base),
                moved_from=from_slot(b.moved_from, base) if b.moved_from is not None else None,
            )
            for b in plan.blocks
        ],
        unmet=[
            UnmetOut(
                intent_id=u.intent_id,
                title=titles[u.intent_id].title if u.intent_id in titles else u.intent_id,
                priority=u.priority,
                shortfall_minutes=u.shortfall_slots * 15,
            )
            for u in plan.unmet
        ],
        busy=[
            BusyIn(
                label=row.label,
                source=row.source,
                start=from_slot(row.start_slot, base),
                end=from_slot(row.end_slot, base),
            )
            for row in rows
        ],
        solve_ms=plan.solve_ms,
        complete=plan.complete,
        generated_at=datetime.now(UTC),
        origin=base,
        horizon_days=settings().horizon_days,
    )


__all__ = ["app", "minutes_to_slots", "timedelta"]
