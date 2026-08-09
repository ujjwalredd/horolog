"""Google Calendar — real events, via the Calendar API, using a stored OAuth token.

Implements the same `CalendarProvider` protocol as `ICSProvider` and
`CalDAVProvider` in `horolog.providers`, so it drops into `_mirror` unchanged:
whatever mirrors the calendar, mirrors it the same way once fetched.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from horolog.domain.events import BusyInterval
from horolog.providers import SyncError, to_interval

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def _parse(value: dict[str, str], zone: ZoneInfo) -> datetime | None:
    """A Calendar API `start`/`end` object: `dateTime` (timed) or `date` (all-day)."""
    if raw := value.get("dateTime"):
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)
    if raw := value.get("date"):
        day = date.fromisoformat(raw)
        return datetime(day.year, day.month, day.day, tzinfo=zone)
    return None


class GoogleCalendarProvider:
    def __init__(self, access_token: str, zone: ZoneInfo) -> None:
        self._token = access_token
        self._zone = zone

    async def fetch(self, origin: datetime, horizon_days: int) -> list[BusyInterval]:
        end = origin + timedelta(days=horizon_days)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    _EVENTS_URL,
                    headers={"Authorization": f"Bearer {self._token}"},
                    params={
                        "timeMin": origin.isoformat(),
                        "timeMax": end.isoformat(),
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 250,
                    },
                )
                if response.status_code == 401:
                    raise SyncError(
                        "Google access token was rejected — reconnect in Calendars & Sync"
                    )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise SyncError(f"could not reach Google Calendar: {exc}") from exc

        out: list[BusyInterval] = []
        for index, item in enumerate(body.get("items", [])):
            if item.get("status") == "cancelled":
                continue
            # "transparent" is Google's free/busy marker — the same signal
            # ICS calls TRANSP:TRANSPARENT, honoured the same way in parse_ics.
            if item.get("transparency") == "transparent":
                continue
            start = _parse(item.get("start", {}), self._zone)
            finish = _parse(item.get("end", {}), self._zone)
            if start is None or finish is None:
                continue
            interval = to_interval(
                f"google-{item.get('id', index)}",
                item.get("summary", "Busy"),
                start,
                finish,
                origin,
                horizon_days,
            )
            if interval:
                out.append(interval)
        return out
