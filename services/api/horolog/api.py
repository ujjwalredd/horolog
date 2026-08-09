"""HTTP surface.

Slots stop at this boundary: everything crossing the wire is an ISO datetime.
The UI never learns that the engine thinks in 15-minute integers.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from horolog import oauth
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
from horolog.domain.intent import DailyWindow, EnergyLevel, Intent, IntentKind, Priority
from horolog.domain.plan import Plan
from horolog.domain.time import (
    SLOT_MINUTES,
    SLOTS_PER_DAY,
    from_slot,
    minutes_to_slots,
    to_slot,
)
from horolog.integrations.github import GithubError, fetch_github_issues
from horolog.integrations.google_calendar import GoogleCalendarProvider
from horolog.integrations.linear import LinearError, fetch_linear_issues
from horolog.integrations.outlook_calendar import OutlookCalendarProvider
from horolog.integrations.todoist import TodoistError, fetch_todoist_tasks
from horolog.llm import AnthropicProvider, ExtractionFailed, OpenAICompatible, Provider
from horolog.providers import (
    BUFFER_SOURCE,
    CalDAVProvider,
    CalendarProvider,
    ICSProvider,
    SyncError,
    decompression_buffers,
    to_ics,
)
from horolog.settings import settings
from horolog.solver.solve import merge_busy, solve

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


def _clip(start: int, end: int) -> tuple[int, int] | None:
    """Trim a span to the horizon, or None if it falls entirely outside it.

    Guards the write path. `BusyInterval` refuses a negative slot, so storing a
    yesterday event — trivially posted by a client in a timezone behind the
    server, or by anyone entering a meeting that has already begun — used to
    make every later read of the plan raise on the way out. The row could then
    only be removed from the database by hand. Feed events have always been
    clipped in `_to_interval`; the hand-entered path just never was.
    """
    lo, hi = max(start, 0), min(end, horizon_slots())
    return (lo, hi) if hi > lo else None


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
    energy: EnergyLevel | None = None
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
            energy=self.energy,
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
    energy: EnergyLevel | None = None
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
    model: str | None = None
    provider: str | None = None
    api_key: str | None = None


@app.post("/api/capture", status_code=201)
async def capture_intent(body: CaptureIn, db: AsyncSession = Depends(session)) -> dict[str, Any]:
    """Natural language in, a scheduled intent out.

    The model's output is a proposal: it is schema-constrained at decode time,
    Pydantic-validated here, and then re-validated by the domain model through
    the ordinary create path. It never reaches a calendar except by way of the
    placer, so the worst a bad extraction can do is create a wrong-looking
    intent the user can delete.
    """
    custom_provider: Provider | None = None
    if body.provider and body.provider != "default" and body.model:
        timeout = settings().llm_timeout_s
        if body.provider == "anthropic":
            custom_provider = AnthropicProvider(body.model, body.api_key or "", timeout)
        else:
            base_url = (
                "https://api.openai.com/v1"
                if body.provider == "openai"
                else settings().llm_base_url
            )
            custom_provider = OpenAICompatible(base_url, body.model, body.api_key or "", timeout)

    try:
        draft = await capture(body.text, provider=custom_provider)
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
    """Replace the hand-entered calendar.

    Stands in for the provider sync layer: whatever is posted becomes the set of
    immovable events. Replacing rather than merging keeps the mirror an exact
    reflection, so a deleted meeting actually frees its slot.

    Scoped to the sources being written. A blanket delete here would silently
    wipe a synced ICS feed and every accepted booking the moment anyone saved a
    manual event — sources are independent mirrors, and each owns only its own
    rows (`_mirror` scopes its delete the same way).
    """
    base = origin()
    touched = {event.source for event in body} | {"manual"}
    await db.execute(delete(BusyRow).where(BusyRow.source.in_(touched)))
    stored = 0
    for event in body:
        if event.end <= event.start:
            raise HTTPException(status_code=422, detail=f"{event.label!r} ends before it starts")
        span = _clip(to_slot(event.start, base), to_slot(event.end, base))
        if span is None:
            continue
        stored += 1
        db.add(
            BusyRow(
                id=uuid.uuid4().hex[:16],
                source=event.source,
                label=event.label,
                start_slot=span[0],
                end_slot=span[1],
            )
        )
    await db.commit()
    plan = await _replan(db)
    return {"events": stored, "blocks": len(plan.blocks)}


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
    return analyse(
        plan,
        await load_intents(db),
        # Merged, because a double-booked calendar would otherwise count the
        # same hour twice and report a meeting load above 100%.
        merge_busy(await _busy(db)),
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


LINEAR_PREFIX = "linear:"
TODOIST_PREFIX = "todoist:"
GITHUB_PREFIX = "github:"


class LinearSyncIn(BaseModel):
    api_key: str = Field(default="", max_length=200)
    """A personal API key, pasted directly. Empty uses the stored OAuth
    connection instead — either path is a legitimate way to authenticate."""
    priority: Priority = Priority.P2
    max_chunk_minutes: int = Field(default=120, gt=0)


async def _resolve_credential(db: AsyncSession, provider: str, pasted: str) -> str:
    """A pasted key wins; otherwise fall back to a stored OAuth connection."""
    if pasted:
        return pasted
    token = await oauth.valid_access_token(db, settings(), provider)
    if not token:
        raise HTTPException(
            status_code=409,
            detail=f"{provider} is not connected — paste a key or connect it in Calendars & Sync",
        )
    return token


@app.post("/api/sync/linear")
async def sync_linear(body: LinearSyncIn, db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Mirror Linear's started issues as schedulable tasks.

    Replace rather than merge, on a stable `linear:<issue-id>` key: an issue
    moved out of progress has to stop consuming time, and reusing the key keeps
    a re-sync from shuffling everything that did not change.
    """
    api_key = await _resolve_credential(db, "linear", body.api_key)
    try:
        issues = await fetch_linear_issues(api_key)
    except LinearError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await db.execute(delete(IntentRow).where(IntentRow.id.startswith(LINEAR_PREFIX)))
    base = origin()
    for issue in issues:
        label = f"{issue.identifier} {issue.title}".strip()
        wire = IntentIn(
            title=label[:200],
            kind=IntentKind.TASK,
            priority=body.priority,
            minutes_per_period=issue.minutes,
            # An issue smaller than the default 30-minute floor would be
            # rejected by the domain model for demanding less than one chunk.
            min_chunk_minutes=min(30, issue.minutes),
            max_chunk_minutes=max(min(body.max_chunk_minutes, issue.minutes), issue.minutes),
        )
        intent = wire.to_domain(f"{LINEAR_PREFIX}{issue.id}", base)
        db.add(IntentRow(id=intent.id, payload=intent.model_dump(mode="json")))
    await db.commit()
    plan = await _replan(db)
    return {"issues": len(issues), "blocks": len(plan.blocks)}


class TokenSyncIn(BaseModel):
    token: str = Field(default="", max_length=500)


async def _sync_tasks(
    db: AsyncSession, prefix: str, kind_label: str, tasks: list[tuple[str, str, Priority, int]]
) -> int:
    """Store a provider's tasks as intents under a stable id prefix.

    Shared by Todoist and GitHub: both reduce to (id, title, priority,
    minutes) tuples, so the storage half — replace-by-prefix, `to_domain`,
    commit — does not need writing twice.
    """
    await db.execute(delete(IntentRow).where(IntentRow.id.startswith(prefix)))
    base = origin()
    for task_id, title, priority, minutes in tasks:
        wire = IntentIn(
            title=f"{kind_label}: {title}"[:200],
            kind=IntentKind.TASK,
            priority=priority,
            minutes_per_period=minutes,
            min_chunk_minutes=min(30, minutes),
            max_chunk_minutes=minutes,
        )
        intent = wire.to_domain(f"{prefix}{task_id}", base)
        db.add(IntentRow(id=intent.id, payload=intent.model_dump(mode="json")))
    await db.commit()
    return len(tasks)


@app.post("/api/sync/todoist")
async def sync_todoist(body: TokenSyncIn, db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Mirror uncompleted Todoist tasks as schedulable intents."""
    token = await _resolve_credential(db, "todoist", body.token)
    try:
        tasks = await fetch_todoist_tasks(token)
    except TodoistError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    count = await _sync_tasks(
        db,
        TODOIST_PREFIX,
        "Todoist",
        [(t.id, t.content, t.priority, t.minutes) for t in tasks],
    )
    plan = await _replan(db)
    return {"tasks": count, "blocks": len(plan.blocks)}


@app.post("/api/sync/github")
async def sync_github(body: TokenSyncIn, db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Mirror assigned open GitHub issues as schedulable intents."""
    token = await _resolve_credential(db, "github", body.token)
    try:
        issues = await fetch_github_issues(token)
    except GithubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    count = await _sync_tasks(
        db,
        GITHUB_PREFIX,
        "GitHub",
        [(i.id, f"#{i.number} {i.title}", Priority.P2, i.minutes) for i in issues],
    )
    plan = await _replan(db)
    return {"issues": count, "blocks": len(plan.blocks)}


@app.post("/api/sync/google")
async def sync_google(db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Mirror real Google Calendar events for the connected account.

    No body: the access token lives server-side (`/api/auth/google` put it
    there), never in a request from the browser.
    """
    token = await _resolve_credential(db, "google", "")
    provider = GoogleCalendarProvider(token, settings().zone)
    return await _mirror(db, provider, "google")


@app.post("/api/sync/outlook")
async def sync_outlook(db: AsyncSession = Depends(session)) -> dict[str, int]:
    """Mirror real Outlook / Microsoft 365 events for the connected account."""
    token = await _resolve_credential(db, "outlook", "")
    provider = OutlookCalendarProvider(token, settings().zone)
    return await _mirror(db, provider, "outlook")


# --------------------------------------------------------------------------
# OAuth connections
# --------------------------------------------------------------------------


@app.get("/api/connections")
async def list_connections(db: AsyncSession = Depends(session)) -> dict[str, bool]:
    """Which providers have a stored, usable token — what the Connect page
    renders as "Connected" instead of guessing from browser state."""
    connected = await oauth.connected_providers(db)
    return {provider: provider in connected for provider in oauth.PROVIDERS}


@app.delete("/api/connections/{provider}")
async def disconnect(provider: str, db: AsyncSession = Depends(session)) -> Response:
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    await oauth.forget_token(db, provider)
    return Response(status_code=204)


def _connect_redirect(web: str, **params: str) -> RedirectResponse:
    """A redirect to the Connect page's status banner.

    `error` in particular carries text from outside the process — the OAuth
    provider's own callback query string, which anyone can hit directly with
    any value they like, not only a real provider. Building the URL with an
    f-string let that value break out of the query string; `urlencode` is what
    keeps it confined to the `error` parameter's value.
    """
    return RedirectResponse(url=f"{web}/connect?{urlencode(params)}")


@app.get("/api/auth/{provider}")
async def auth_redirect(provider: str) -> RedirectResponse:
    cfg = settings()
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")

    client_id, client_secret = oauth.client_credentials(cfg, provider)
    if not client_id or not client_secret:
        return _connect_redirect(
            cfg.public_web_url, status="credentials_missing", provider=provider
        )
    state = oauth.new_state()
    return RedirectResponse(url=oauth.authorize_url(cfg, provider, state))


@app.get("/api/auth/callback/{provider}")
async def auth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(session),
) -> RedirectResponse:
    cfg = settings()
    web = cfg.public_web_url
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    if error:
        return _connect_redirect(web, status="error", error=error)
    if not code or not state or not oauth.consume_state(state):
        # A missing or already-used state is what a replayed or forged
        # callback looks like — reject it rather than trust a bare code.
        return _connect_redirect(
            web, status="error", error="Invalid or expired authorization request"
        )

    try:
        token = await oauth.exchange_code(cfg, provider, code)
    except oauth.OAuthError as exc:
        return _connect_redirect(web, status="error", error=str(exc))

    await oauth.save_token(db, provider, token)
    # The token stays server-side — never appended here, never handed to the
    # browser. The frontend learns the connection succeeded and asks the
    # relevant /api/sync/* endpoint to use it.
    return _connect_redirect(web, status="success", provider=provider)


# --------------------------------------------------------------------------
# Booking links
# --------------------------------------------------------------------------

MIN_BOOKING_MINUTES = 15
MAX_BOOKING_MINUTES = 8 * 60


class FreeSlot(BaseModel):
    start: datetime
    end: datetime


@app.get("/api/availability")
async def availability(
    minutes: int = 30, days: int = 7, db: AsyncSession = Depends(session)
) -> list[FreeSlot]:
    """Openings a guest may book, inside the configured working window.

    "True free time": only real commitments close a slot. Horolog's own blocks
    are movable by construction, so offering an hour that currently holds focus
    time is not a double-booking — accepting it pushes that focus time
    elsewhere. Hiding those hours would hand a booking link a calendar that
    looks full while the day is actually open, which is the exact failure the
    scheduler exists to prevent.
    """
    if not MIN_BOOKING_MINUTES <= minutes <= MAX_BOOKING_MINUTES:
        raise HTTPException(
            status_code=422,
            detail=f"minutes must be between {MIN_BOOKING_MINUTES} and {MAX_BOOKING_MINUTES}",
        )
    cfg = settings()
    if not 1 <= days <= cfg.horizon_days:
        raise HTTPException(
            status_code=422, detail=f"days must be between 1 and {cfg.horizon_days}"
        )

    base = origin()
    need = minutes_to_slots(minutes)
    taken = bytearray(days * SLOTS_PER_DAY)
    for event in merge_busy(await _busy(db)):
        for slot in range(max(event.start_slot, 0), min(event.end_slot, len(taken))):
            taken[slot] = 1

    # Nothing in the past: `origin` is midnight, so most of today is behind us.
    now_slot = to_slot(datetime.now(cfg.zone), base)
    window = (cfg.workday_start_min // SLOT_MINUTES, cfg.workday_end_min // SLOT_MINUTES)
    out: list[FreeSlot] = []
    for day in range(days):
        day_lo = day * SLOTS_PER_DAY
        # Step by the meeting length so the offered slots tile the day rather
        # than overlap — two adjacent offers that cannot both be taken are a
        # booking page that contradicts itself.
        for start in range(day_lo + window[0], day_lo + window[1] - need + 1, need):
            if start < now_slot or any(taken[start : start + need]):
                continue
            out.append(FreeSlot(start=from_slot(start, base), end=from_slot(start + need, base)))
    return out


class BookIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=200)
    start: LocalDateTime
    minutes: int = 30


class _RateLimiter:
    """A fixed window per key. Everything else here has no auth by design —
    a self-hosted single-user tool has no accounts to protect — but a booking
    link is deliberately the one URL meant to be handed to strangers, and
    unlike the rest of the API it writes to the calendar on every call. That
    combination is worth a floor.

    ponytail: in-process, unbounded by IP count. Fine for what a booking page
    actually receives; move to a real store if this ever runs multi-worker.
    """

    def __init__(self, limit: int, window_s: float) -> None:
        self._limit = limit
        self._window_s = window_s
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_s
        recent = [t for t in self._hits.get(key, []) if t > cutoff]
        if len(recent) >= self._limit:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True


_booking_limiter = _RateLimiter(limit=5, window_s=600)
"""5 bookings per IP per 10 minutes — enough for a real guest picking a slot,
retrying after a race, and correcting a typo; not enough to fill a calendar."""


@app.post("/api/book", status_code=201)
async def book(
    body: BookIn, request: Request, db: AsyncSession = Depends(session)
) -> dict[str, Any]:
    """Accept a booking from a shared link.

    The booking lands in the busy mirror, not the intent list, because a guest's
    commitment is exactly as immovable as any other real meeting — that is what
    makes the surrounding flexible work reschedule around it instead of the
    other way round.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _booking_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="too many booking attempts, try again shortly")
    if not MIN_BOOKING_MINUTES <= body.minutes <= MAX_BOOKING_MINUTES:
        raise HTTPException(status_code=422, detail="unsupported meeting length")

    base = origin()
    start = to_slot(body.start, base)
    end = start + minutes_to_slots(body.minutes)
    if start < to_slot(datetime.now(settings().zone), base):
        raise HTTPException(status_code=409, detail="that time has already passed")
    if end > horizon_slots():
        raise HTTPException(
            status_code=422,
            detail=f"bookings only go {settings().horizon_days} days out",
        )
    for event in merge_busy(await _busy(db)):
        if start < event.end_slot and event.start_slot < end:
            raise HTTPException(
                status_code=409, detail="that slot was taken while you were choosing"
            )

    who = f"{body.name} <{body.email}>" if body.email else body.name
    db.add(
        BusyRow(
            id=f"booking:{uuid.uuid4().hex[:12]}",
            source="booking",
            label=f"Booked: {who}"[:200],
            start_slot=start,
            end_slot=end,
        )
    )
    await db.commit()
    plan = await _replan(db)
    return {
        "start": from_slot(start, base).isoformat(),
        "end": from_slot(end, base).isoformat(),
        "rescheduled_blocks": sum(1 for b in plan.blocks if b.moved_from is not None),
    }


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


async def _busy(db: AsyncSession) -> list[BusyInterval]:
    """Every interval the calendar is already spoken for.

    The single place the mirror is read, so the solver, the analytics page, the
    booking page and the planner grid can never disagree about what is occupied.
    Decompression buffers are derived here rather than stored: they are a
    function of the meetings, and persisting them would leave orphans behind
    every time a meeting moved.
    """
    rows = (await db.execute(select(BusyRow))).scalars().all()
    busy = [
        BusyInterval(
            source_id=row.id, start_slot=row.start_slot, end_slot=row.end_slot, label=row.label
        )
        for row in rows
    ]
    cfg = settings()
    if cfg.auto_buffer_enabled:
        busy += decompression_buffers(busy, cfg.auto_buffer_minutes)
    return busy


async def _replan(db: AsyncSession) -> Plan:
    intents = await load_intents(db)
    plan = solve(intents, await _busy(db), horizon_slots(), previous=await load_previous_plan(db))
    await save_plan(db, plan)
    bus.publish(json.dumps({"blocks": len(plan.blocks), "solve_ms": round(plan.solve_ms, 2)}))
    return plan


async def _render(db: AsyncSession, plan: Plan) -> PlanOut:
    base = origin()
    titles = {i.id: i for i in await load_intents(db)}
    rows = (await db.execute(select(BusyRow))).scalars().all()
    sources = {row.id: row.source for row in rows}
    return PlanOut(
        blocks=[
            BlockOut(
                intent_id=b.intent_id,
                title=titles[b.intent_id].title if b.intent_id in titles else b.intent_id,
                kind=titles[b.intent_id].kind if b.intent_id in titles else IntentKind.TASK,
                priority=b.priority,
                energy=titles[b.intent_id].energy if b.intent_id in titles else None,
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
                label=event.label,
                # Derived buffers have no row of their own; the grid still has
                # to show them, or time disappears with no visible reason.
                source=sources.get(event.source_id, BUFFER_SOURCE),
                start=from_slot(event.start_slot, base),
                end=from_slot(event.end_slot, base),
            )
            for event in await _busy(db)
        ],
        solve_ms=plan.solve_ms,
        complete=plan.complete,
        generated_at=datetime.now(UTC),
        origin=base,
        horizon_days=settings().horizon_days,
    )


__all__ = ["app", "minutes_to_slots", "timedelta"]
