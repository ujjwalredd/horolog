"""Zoom Server-to-Server OAuth: create a no-fixed-time meeting for a Smart
Meeting intent, and clean it up if the intent is deleted.

Server-to-Server OAuth (the `account_credentials` grant), not the
user-delegated authorization-code flow `oauth.py` uses for calendars — Zoom's
own docs recommend Server-to-Server specifically for backend automation like
this, and it needs no browser redirect, which fits a single self-hosted user
better than sending them through a consent screen for their own account.

Every meeting is created with `type: 8` ("recurring, no fixed time"): it needs
no start time up front and its `join_url` never expires, so the link stays
correct no matter what slot the solver picks or how a later re-solve moves the
block — nothing here has to stay in sync with the placement engine.
"""

from __future__ import annotations

import base64
import time

import httpx
from pydantic import BaseModel

from horolog.settings import Settings

_TOKEN_URL = "https://zoom.us/oauth/token"
_API_BASE = "https://api.zoom.us/v2"


class ZoomError(RuntimeError):
    """Zoom could not be reached, or rejected the request. Message is fit to
    show a user — though every caller here treats this as best-effort and
    logs it rather than letting it block scheduling."""


class ZoomMeeting(BaseModel):
    id: str
    join_url: str


# Keyed by account id so a credential change during the process's lifetime
# (unusual, but `settings()` can be re-read) can't serve a stale token from a
# different account.
_token_cache: dict[str, tuple[str, float]] = {}


async def _access_token(cfg: Settings, timeout: float = 15.0) -> str:
    cached = _token_cache.get(cfg.zoom_account_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]

    basic = base64.b64encode(f"{cfg.zoom_client_id}:{cfg.zoom_client_secret}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _TOKEN_URL,
                params={"grant_type": "account_credentials", "account_id": cfg.zoom_account_id},
                headers={"Authorization": f"Basic {basic}"},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise ZoomError(f"could not reach Zoom: {exc}") from exc
    except ValueError as exc:
        raise ZoomError("Zoom returned something that was not JSON") from exc

    token = str(body.get("access_token") or "")
    if not token:
        raise ZoomError("Zoom did not return an access token")
    # A slight early margin, same reasoning as oauth.py's own token refresh:
    # a token that expires mid-request is worse than refreshing 60s early.
    expires_in = body.get("expires_in")
    ttl = int(expires_in) - 60 if isinstance(expires_in, int | float) else 0
    _token_cache[cfg.zoom_account_id] = (token, time.monotonic() + max(ttl, 0))
    return token


async def create_meeting(cfg: Settings, topic: str, timeout: float = 15.0) -> ZoomMeeting:
    token = await _access_token(cfg, timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{_API_BASE}/users/me/meetings",
                json={"topic": topic[:200], "type": 8},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise ZoomError(f"Zoom rejected the meeting: {exc}") from exc
    except ValueError as exc:
        raise ZoomError("Zoom returned something that was not JSON") from exc

    meeting_id = body.get("id")
    join_url = body.get("join_url")
    if not meeting_id or not join_url:
        raise ZoomError("Zoom's response was missing an id or join_url")
    return ZoomMeeting(id=str(meeting_id), join_url=str(join_url))


async def delete_meeting(cfg: Settings, meeting_id: str, timeout: float = 15.0) -> None:
    token = await _access_token(cfg, timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.delete(
                f"{_API_BASE}/meetings/{meeting_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            # 404 means it's already gone — not this call's problem to raise on.
            if response.status_code != 404:
                response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ZoomError(f"could not remove the Zoom meeting: {exc}") from exc
