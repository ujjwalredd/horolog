"""Outlook / Microsoft 365 — real events, via Microsoft Graph, using a stored
OAuth token. Same `CalendarProvider` shape as `google_calendar.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from horolog.domain.events import BusyInterval
from horolog.providers import SyncError, to_interval

_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/calendarview"

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
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    _EVENTS_URL,
                    headers={"Authorization": f"Bearer {self._token}", **_HEADERS},
                    params={
                        "startDateTime": origin.astimezone(ZoneInfo("UTC")).isoformat(),
                        "endDateTime": end.astimezone(ZoneInfo("UTC")).isoformat(),
                        "$top": 250,
                        "$select": "id,subject,start,end,showAs,isCancelled",
                    },
                )
                if response.status_code == 401:
                    raise SyncError(
                        "Microsoft access token was rejected — reconnect in Calendars & Sync"
                    )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise SyncError(f"could not reach Microsoft Graph: {exc}") from exc

        out: list[BusyInterval] = []
        for index, item in enumerate(body.get("value", [])):
            if item.get("isCancelled") or item.get("showAs") in ("free", "workingElsewhere"):
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
        return out
