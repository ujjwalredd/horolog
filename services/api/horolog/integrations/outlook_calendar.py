"""Outlook / Microsoft 365 — real events, via Microsoft Graph, using a stored
OAuth token. `OutlookCalendarProvider` is the same `CalendarProvider` shape as
`google_calendar.py`'s; `OutlookCalendarWriter` is the write-back counterpart,
same reasoning as `GoogleCalendarWriter`'s docstring — a dedicated secondary
calendar, never the default one Graph's `calendarview` reads.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from horolog.domain.events import BusyInterval
from horolog.providers import SyncError, to_interval

_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/calendarview"
_CALENDARS_URL = "https://graph.microsoft.com/v1.0/me/calendars"
CALENDAR_NAME = "Horolog"

MAX_PAGES = 10
"""Bounds both `fetch` and `ensure_calendar`'s pagination — same convention as
`google_calendar.py`'s."""

# Graph returns each event in whatever zone `start.timeZone` names, which
# varies per calendar; asking for UTC on every response removes that
# variable so parsing here doesn't need a per-event zone table.
_HEADERS = {"Prefer": 'outlook.timezone="UTC"'}


def _parse(value: dict[str, str]) -> datetime | None:
    raw = value.get("dateTime")
    if not raw:
        return None
    # Graph's `dateTime` has no offset ("2026-08-10T14:00:00.0000000"); the
    # Prefer header above is what makes "no offset" mean UTC specifically.
    return datetime.fromisoformat(raw).replace(tzinfo=ZoneInfo("UTC"))


class OutlookCalendarProvider:
    def __init__(self, access_token: str, zone: ZoneInfo) -> None:
        self._token = access_token
        self._zone = zone

    async def fetch(self, origin: datetime, horizon_days: int) -> list[BusyInterval]:
        end = origin + timedelta(days=horizon_days)
        out: list[BusyInterval] = []
        url: str | None = _EVENTS_URL
        params: dict[str, str | int] | None = {
            "startDateTime": origin.astimezone(ZoneInfo("UTC")).isoformat(),
            "endDateTime": end.astimezone(ZoneInfo("UTC")).isoformat(),
            "$top": 250,
            "$select": "id,subject,start,end,showAs,isCancelled",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                for _ in range(MAX_PAGES):
                    assert url is not None  # loop only continues once a next link is found
                    response = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {self._token}", **_HEADERS},
                        params=params,
                    )
                    if response.status_code == 401:
                        raise SyncError(
                            "Microsoft access token was rejected — reconnect in Calendars & Sync"
                        )
                    response.raise_for_status()
                    body = response.json()
                    for index, item in enumerate(body.get("value", [])):
                        if item.get("isCancelled") or item.get("showAs") in (
                            "free",
                            "workingElsewhere",
                        ):
                            continue
                        start = _parse(item.get("start", {}))
                        finish = _parse(item.get("end", {}))
                        if start is None or finish is None:
                            continue
                        interval = to_interval(
                            f"outlook-{item.get('id', index)}",
                            item.get("subject", "Busy"),
                            start,
                            finish,
                            origin,
                            horizon_days,
                        )
                        if interval:
                            out.append(interval)
                    # Once a `@odata.nextLink` is followed, it already carries
                    # every query param — passing `params` again would append
                    # a second, conflicting copy.
                    url = body.get("@odata.nextLink")
                    params = None
                    if not url:
                        break
        except httpx.HTTPError as exc:
            raise SyncError(f"could not reach Microsoft Graph: {exc}") from exc
        return out


class OutlookCalendarWriter:
    """Pushes scheduled blocks onto a dedicated "Horolog" secondary calendar."""

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _check_auth(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise SyncError(
                "Microsoft rejected the write-back request — reconnect Outlook in "
                "Calendars & Sync to grant calendar write access"
            )

    async def ensure_calendar(self, client: httpx.AsyncClient) -> str:
        """Find or create the "Horolog" calendar; return its id. Resolved fresh
        on every push — see `GoogleCalendarWriter.ensure_calendar`'s docstring."""
        url: str | None = _CALENDARS_URL
        for _ in range(MAX_PAGES):
            assert url is not None  # loop only continues once a next link is found
            response = await client.get(url, headers=self._headers)
            self._check_auth(response)
            response.raise_for_status()
            body = response.json()
            for item in body.get("value", []):
                if item.get("name") == CALENDAR_NAME:
                    return str(item["id"])
            url = body.get("@odata.nextLink")
            if not url:
                break

        response = await client.post(
            _CALENDARS_URL, headers=self._headers, json={"name": CALENDAR_NAME}
        )
        self._check_auth(response)
        response.raise_for_status()
        return str(response.json()["id"])

    @staticmethod
    def _body(start: datetime, end: datetime) -> dict[str, dict[str, str]]:
        # Graph wants a naive dateTime paired with an explicit timeZone
        # rather than an offset baked into the string.
        return {
            "start": {
                "dateTime": start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None).isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None).isoformat(),
                "timeZone": "UTC",
            },
        }

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
            json={"subject": title, **self._body(start, end)},
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
            json=self._body(start, end),
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
