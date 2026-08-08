"""Calendar providers — where the immovable events come from.

A genuine two-implementation abstraction:

    ICS      a file or a subscription URL. Every calendar on earth exports one,
             including Google and Outlook ("secret address in iCal format"), so
             this covers the common case with no OAuth and no public callback.
    CalDAV   a live server (Radicale, Nextcloud, Fastmail, iCloud, Zimbra) —
             read-write, and the only path that is fully self-hostable offline.

Both collapse to the same thing the scheduler wants: a list of slots that are
already spoken for.

Recurrence is expanded, not skipped. A weekly standup stored as one VEVENT with
an RRULE is one row and fifty-two occupied hours; treating it as a single event
would leave the scheduler booking straight through every instance but the first.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from horolog.domain.events import BusyInterval
from horolog.domain.time import to_slot


class SyncError(RuntimeError):
    """The calendar could not be read. Carries a message fit to show a user."""


class CalendarProvider(Protocol):
    async def fetch(self, origin: datetime, horizon_days: int) -> list[BusyInterval]:
        """Occupied intervals between `origin` and the end of the horizon."""
        ...


def _as_datetime(value: object, zone: ZoneInfo) -> datetime | None:
    """Normalise an icalendar date/datetime to an aware datetime.

    All-day events arrive as `date`, not `datetime`, and a naive comparison
    against them raises. Floating times (no tzinfo) are read in the calendar's
    own zone, which is what "floating" means.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=zone)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=zone)
    return None


def _to_interval(
    source_id: str, label: str, start: datetime, end: datetime, origin: datetime, horizon: int
) -> BusyInterval | None:
    """Clip an event to the horizon and convert it to slots, or drop it."""
    limit = origin + timedelta(days=horizon)
    if end <= origin or start >= limit:
        return None
    lo = to_slot(max(start, origin), origin)
    hi = to_slot(min(end, limit), origin)
    if hi <= lo:
        # Sub-slot or zero-length events (reminders, pinned markers) occupy no
        # schedulable time; keeping them would create empty intervals the
        # domain model rejects.
        return None
    return BusyInterval(source_id=source_id, start_slot=lo, end_slot=hi, label=label[:200])


def parse_ics(text: str, origin: datetime, horizon_days: int, zone: ZoneInfo) -> list[BusyInterval]:
    """Expand an iCalendar document into occupied intervals."""
    try:
        import icalendar
        import recurring_ical_events
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise SyncError("ICS support needs `icalendar` and `recurring-ical-events`") from exc

    try:
        calendar = icalendar.Calendar.from_ical(text)
    except Exception as exc:
        raise SyncError(f"could not parse that calendar: {exc}") from exc

    end = origin + timedelta(days=horizon_days)
    out: list[BusyInterval] = []
    # Expands RRULE/RDATE and applies EXDATE and modified instances.
    for index, event in enumerate(recurring_ical_events.of(calendar).between(origin, end)):
        # TRANSP:TRANSPARENT means "I am free during this" — free/busy markers,
        # holidays, focus placeholders. Honouring it is the difference between
        # mirroring a calendar and mirroring a to-do list.
        if str(event.get("TRANSP", "OPAQUE")).upper() == "TRANSPARENT":
            continue
        if str(event.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = _as_datetime(getattr(event.get("DTSTART"), "dt", None), zone)
        finish = _as_datetime(getattr(event.get("DTEND"), "dt", None), zone)
        if start is None:
            continue
        if finish is None:
            duration = getattr(event.get("DURATION"), "dt", None)
            finish = (
                start + duration if isinstance(duration, timedelta) else start + timedelta(hours=1)
            )
        uid = str(event.get("UID", f"ics-{index}"))
        interval = _to_interval(
            f"{uid}-{index}", str(event.get("SUMMARY", "Busy")), start, finish, origin, horizon_days
        )
        if interval:
            out.append(interval)
    return out


class ICSProvider:
    """A published .ics URL or a pasted file.

    The zero-configuration path: every calendar app can emit one, so this works
    against Google and Outlook without an OAuth app, a verified domain, or a
    publicly reachable webhook endpoint.
    """

    def __init__(self, url: str, zone: ZoneInfo, timeout: float = 30.0) -> None:
        self._url = url
        self._zone = zone
        self._timeout = timeout

    async def fetch(self, origin: datetime, horizon_days: int) -> list[BusyInterval]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as http:
                # webcal:// is the same document over https; every calendar app
                # hands out that scheme and no HTTP client understands it.
                url = self._url.replace("webcal://", "https://", 1)
                response = await http.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SyncError(f"could not fetch the calendar: {exc}") from exc
        return parse_ics(response.text, origin, horizon_days, self._zone)


class CalDAVProvider:
    """A live CalDAV server.

    Expansion is asked of the server (`expand=True`) rather than done here: the
    server already knows the recurrence rules and its own timezone database, and
    a busy calendar answers in one round trip instead of shipping every master
    event across the wire.
    """

    def __init__(self, url: str, username: str, password: str, zone: ZoneInfo) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._zone = zone

    async def fetch(self, origin: datetime, horizon_days: int) -> list[BusyInterval]:
        import asyncio

        # The `caldav` client is synchronous; run it off the event loop so a slow
        # or unreachable server cannot stall every other request in the process.
        return await asyncio.to_thread(self._fetch_blocking, origin, horizon_days)

    def _fetch_blocking(self, origin: datetime, horizon_days: int) -> list[BusyInterval]:
        try:
            import caldav
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise SyncError("CalDAV support needs the `caldav` package") from exc

        end = origin + timedelta(days=horizon_days)
        out: list[BusyInterval] = []
        try:
            client = caldav.DAVClient(
                url=self._url, username=self._username, password=self._password
            )
            for calendar in client.principal().calendars():
                for index, event in enumerate(
                    calendar.search(start=origin, end=end, event=True, expand=True)
                ):
                    component = event.icalendar_component
                    if component is None:
                        continue
                    if str(component.get("TRANSP", "OPAQUE")).upper() == "TRANSPARENT":
                        continue
                    start = _as_datetime(getattr(component.get("DTSTART"), "dt", None), self._zone)
                    finish = _as_datetime(getattr(component.get("DTEND"), "dt", None), self._zone)
                    if start is None:
                        continue
                    if finish is None:
                        finish = start + timedelta(hours=1)
                    uid = str(component.get("UID", f"caldav-{index}"))
                    interval = _to_interval(
                        f"{uid}-{index}",
                        str(component.get("SUMMARY", "Busy")),
                        start,
                        finish,
                        origin,
                        horizon_days,
                    )
                    if interval:
                        out.append(interval)
        except SyncError:
            raise
        except Exception as exc:
            raise SyncError(f"CalDAV sync failed: {exc}") from exc
        return out


def _escape(text: str) -> str:
    """RFC 5545 §3.3.11 text escaping.

    An unescaped comma silently truncates SUMMARY in most clients — the
    backslash has to be doubled first, or it escapes the escapes.
    """
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def to_ics(plan_blocks: list[tuple[str, datetime, datetime]], name: str = "Horolog") -> str:
    """Export scheduled blocks as an iCalendar feed.

    Lets any calendar app subscribe to the plan read-only — the simplest useful
    write path, and the one that cannot corrupt the user's real calendar.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Horolog//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{name}",
    ]
    stamp = datetime.now(tz=ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    for index, (title, start, end) in enumerate(plan_blocks):
        lines += [
            "BEGIN:VEVENT",
            f"UID:horolog-{index}-{int(start.timestamp())}@horolog",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{end.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}",
            # Escaping per RFC 5545 §3.3.11 — an unescaped comma in a title
            # silently truncates the field in most clients.
            f"SUMMARY:{_escape(title)}",
            "TRANSP:OPAQUE",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
