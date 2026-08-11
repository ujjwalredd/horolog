"""Google Calendar — real events, via the Calendar API, using a stored OAuth token.

`GoogleCalendarProvider` implements the same `CalendarProvider` protocol as
`ICSProvider` and `CalDAVProvider` in `horolog.providers`, so it drops into
`_mirror` unchanged: whatever mirrors the calendar, mirrors it the same way
once fetched.

`GoogleCalendarWriter` is the other direction — pushing the plan back out as
real events, on a dedicated secondary calendar rather than the primary one.
See `api.py`'s `_push_calendar` for why: a secondary calendar is structurally
invisible to `GoogleCalendarProvider.fetch` (which reads `calendars/primary`),
so what Horolog writes can never come back around as busy time it then
schedules around.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from horolog.domain.events import BusyInterval
from horolog.providers import SyncError, to_interval

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
_CALENDARS_URL = "https://www.googleapis.com/calendar/v3/calendars"
CALENDAR_NAME = "Horolog"

MAX_PAGES = 10
"""Bounds both `fetch` and `ensure_calendar`'s pagination — a hard cap on
pages, not on events/calendars found, matching the convention already used
for tracker syncs (see `integrations/notion.py`)."""


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
        out: list[BusyInterval] = []
        page_token: str | None = None
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                for _ in range(MAX_PAGES):
                    params: dict[str, str | int] = {
                        "timeMin": origin.isoformat(),
                        "timeMax": end.isoformat(),
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 250,
                    }
                    if page_token:
                        params["pageToken"] = page_token
                    response = await client.get(
                        _EVENTS_URL,
                        headers={"Authorization": f"Bearer {self._token}"},
                        params=params,
                    )
                    if response.status_code == 401:
                        raise SyncError(
                            "Google access token was rejected — reconnect in Calendars & Sync"
                        )
                    response.raise_for_status()
                    body = response.json()
                    for index, item in enumerate(body.get("items", [])):
                        if item.get("status") == "cancelled":
                            continue
                        # "transparent" is Google's free/busy marker — the same
                        # signal ICS calls TRANSP:TRANSPARENT, honoured the
                        # same way in parse_ics.
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
                    page_token = body.get("nextPageToken")
                    if not page_token:
                        break
        except httpx.HTTPError as exc:
            raise SyncError(f"could not reach Google Calendar: {exc}") from exc
        return out


class GoogleCalendarWriter:
    """Pushes scheduled blocks onto a dedicated "Horolog" secondary calendar.

    Never touches the primary calendar — combined with the `calendar.app.created`
    OAuth scope (see `oauth.py`), which grants access only to calendars this
    application itself created, a bug here cannot reach anything else on the
    user's account even in principle.
    """

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _check_auth(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise SyncError(
                "Google rejected the write-back request — reconnect Google in "
                "Calendars & Sync to grant calendar write access"
            )

    async def ensure_calendar(self, client: httpx.AsyncClient) -> str:
        """Find or create the "Horolog" calendar; return its id.

        Resolved fresh on every push rather than cached: the only cost is one
        extra GET, and it means a user deleting the calendar in Google is
        self-healing on the next push instead of erroring forever.
        """
        page_token: str | None = None
        for _ in range(MAX_PAGES):
            params: dict[str, str] = {"minAccessRole": "owner"}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(_CALENDAR_LIST_URL, headers=self._headers, params=params)
            self._check_auth(response)
            response.raise_for_status()
            body = response.json()
            for item in body.get("items", []):
                if item.get("summary") == CALENDAR_NAME:
                    return str(item["id"])
            page_token = body.get("nextPageToken")
            if not page_token:
                break

        response = await client.post(
            _CALENDARS_URL, headers=self._headers, json={"summary": CALENDAR_NAME}
        )
        self._check_auth(response)
        response.raise_for_status()
        return str(response.json()["id"])

    async def create_event(
        self,
        client: httpx.AsyncClient,
        calendar_id: str,
        title: str,
        start: datetime,
        end: datetime,
    ) -> str:
        response = await client.post(
            f"{_CALENDARS_URL}/{calendar_id}/events",
            headers=self._headers,
            json={
                "summary": title,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            },
        )
        self._check_auth(response)
        response.raise_for_status()
        return str(response.json()["id"])

    async def patch_event(
        self,
        client: httpx.AsyncClient,
        calendar_id: str,
        event_id: str,
        start: datetime,
        end: datetime,
    ) -> None:
        response = await client.patch(
            f"{_CALENDARS_URL}/{calendar_id}/events/{event_id}",
            headers=self._headers,
            json={"start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}},
        )
        if response.status_code == 404:
            return  # already gone upstream — nothing to move
        self._check_auth(response)
        response.raise_for_status()

    async def delete_event(
        self, client: httpx.AsyncClient, calendar_id: str, event_id: str
    ) -> None:
        response = await client.delete(
            f"{_CALENDARS_URL}/{calendar_id}/events/{event_id}", headers=self._headers
        )
        if response.status_code in (404, 410):
            return  # already gone upstream
        self._check_auth(response)
        response.raise_for_status()
