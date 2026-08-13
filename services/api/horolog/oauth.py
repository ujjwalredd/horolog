"""OAuth authorization-code exchange and token storage.

Every provider button on the Connect page goes through the same four steps:
build an authorize URL with a fresh CSRF state, redirect the browser to it,
exchange the code the provider sends back for a token, and store that token
server-side. This module is that flow, written once, so a connection is either
fully wired — real request, real token, real refresh — or the button for it
does not exist. There is no third state where a button "connects" without a
provider on the other end.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from horolog.db import OAuthTokenRow
from horolog.settings import Settings

CALENDAR_PROVIDERS = ("google", "outlook")
TRACKER_PROVIDERS = ("linear", "todoist", "github")
PROVIDERS = CALENDAR_PROVIDERS + TRACKER_PROVIDERS

_AUTH_URLS = {
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
    "outlook": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    "linear": "https://linear.app/oauth/authorize",
    "todoist": "https://todoist.com/oauth/authorize",
    "github": "https://github.com/login/oauth/authorize",
}

_TOKEN_URLS = {
    "google": "https://oauth2.googleapis.com/token",
    "outlook": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "linear": "https://api.linear.app/oauth/token",
    "todoist": "https://todoist.com/oauth/access_token",
    "github": "https://github.com/login/oauth/access_token",
}

# Requesting a refresh token (`access_type=offline&prompt=consent` for Google,
# `offline_access` for Microsoft) is what makes the connection outlive the
# ~1 hour access token. Linear, Todoist and GitHub tokens issued through OAuth
# do not expire under normal use, so there is nothing to refresh there.
_SCOPES = {
    # `calendar.app.created` grants write access only to calendars this
    # application itself created — never the primary calendar — which is
    # what makes push write-back (`api.py`'s `_push_calendar`) safe by
    # construction rather than by convention. Requesting it here even though
    # write-back defaults to off (`HOROLOG_CALENDAR_WRITEBACK`) means turning
    # write-back on later never needs a second consent screen.
    "google": "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/calendar.app.created",
    # Graph has no equivalent "only what we created" scope, so write-back
    # needs full `Calendars.ReadWrite` — documented plainly in the README
    # rather than glossed over.
    "outlook": "offline_access https://graph.microsoft.com/Calendars.ReadWrite",
    "linear": "read",
    "todoist": "data:read",
    "github": "repo",
}
"""Changing either calendar scope requires every existing Google/Outlook
connection to be reconnected — a token issued under the old scope keeps
working for read sync but is rejected by the write-back endpoints until then.
See CHANGELOG.md 0.2.0."""

REFRESHABLE = {"google", "outlook"}


class OAuthError(RuntimeError):
    """The provider rejected the flow. Message is fit to show a user."""


def client_credentials(cfg: Settings, provider: str) -> tuple[str, str]:
    return {
        "google": (cfg.google_client_id, cfg.google_client_secret),
        "outlook": (cfg.outlook_client_id, cfg.outlook_client_secret),
        "linear": (cfg.linear_client_id, cfg.linear_client_secret),
        "todoist": (cfg.todoist_client_id, cfg.todoist_client_secret),
        "github": (cfg.github_client_id, cfg.github_client_secret),
    }[provider]


def redirect_uri(cfg: Settings, provider: str) -> str:
    return f"{cfg.public_api_url}/api/auth/callback/{provider}"


# --------------------------------------------------------------------------
# CSRF state
# --------------------------------------------------------------------------

_STATE_TTL_S = 600
# ponytail: in-memory, single-process. A callback landing on a different API
# worker than the one that issued the state would fail to validate; fine for
# the one-process deployment this app ships as, move to the database (a row
# per state, like the token table) if that ever changes.
_states: dict[str, float] = {}


def new_state() -> str:
    token = secrets.token_urlsafe(24)
    _states[token] = time.monotonic() + _STATE_TTL_S
    _sweep()
    return token


def consume_state(token: str) -> bool:
    """True once, for a state issued in the last ten minutes. False after."""
    expiry = _states.pop(token, None)
    return expiry is not None and expiry >= time.monotonic()


def _sweep() -> None:
    now = time.monotonic()
    for token in [t for t, expiry in _states.items() if expiry < now]:
        del _states[token]


# --------------------------------------------------------------------------
# Authorize + exchange
# --------------------------------------------------------------------------


def authorize_url(cfg: Settings, provider: str, state: str) -> str:
    client_id, _ = client_credentials(cfg, provider)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(cfg, provider),
        "response_type": "code",
        "scope": _SCOPES[provider],
        "state": state,
    }
    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return f"{_AUTH_URLS[provider]}?{urlencode(params)}"


async def exchange_code(cfg: Settings, provider: str, code: str) -> dict[str, Any]:
    client_id, client_secret = client_credentials(cfg, provider)
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri(cfg, provider),
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _TOKEN_URLS[provider], data=payload, headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise OAuthError(f"{provider} rejected the token exchange: {exc}") from exc
    except ValueError as exc:
        raise OAuthError(f"{provider} returned something that was not JSON") from exc

    if not body.get("access_token"):
        raise OAuthError(body.get("error_description") or body.get("error") or "no token returned")
    return dict(body)


async def _refresh(cfg: Settings, provider: str, refresh_token: str) -> dict[str, Any]:
    client_id, client_secret = client_credentials(cfg, provider)
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if provider == "outlook":
        payload["scope"] = _SCOPES[provider]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _TOKEN_URLS[provider], data=payload, headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            body = dict(response.json())
    except httpx.HTTPError as exc:
        raise OAuthError(f"{provider} token refresh failed: {exc}") from exc
    if not body.get("access_token"):
        raise OAuthError(body.get("error_description") or body.get("error") or "no token returned")
    return body


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


async def save_token(db: AsyncSession, provider: str, token: dict[str, Any]) -> None:
    expires_at = None
    if expires_in := token.get("expires_in"):
        # A slight early margin: a token that expires with 10s left on it and
        # gets used mid-request is worse than refreshing 60s before it needs to.
        expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in) - 60)

    row = await db.get(OAuthTokenRow, provider)
    if row is None:
        row = OAuthTokenRow(provider=provider, access_token="")
        db.add(row)
    row.access_token = token["access_token"]
    # A refresh exchange does not always hand back a new refresh token —
    # Google in particular only does on first consent — so keep the old one
    # rather than overwriting it with nothing.
    if token.get("refresh_token"):
        row.refresh_token = token["refresh_token"]
    row.expires_at = expires_at
    await db.commit()


async def forget_token(db: AsyncSession, provider: str) -> bool:
    row = await db.get(OAuthTokenRow, provider)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def connected_providers(db: AsyncSession) -> set[str]:
    rows = (await db.execute(select(OAuthTokenRow.provider))).scalars().all()
    return set(rows)


async def valid_access_token(db: AsyncSession, cfg: Settings, provider: str) -> str | None:
    """A usable access token for `provider`, refreshing first if it has expired.

    None means "not connected" — the caller's job to turn into a 409, not this
    function's, since what that should look like differs by endpoint.
    """
    row = await db.get(OAuthTokenRow, provider)
    if row is None:
        return None
    # SQLite has no native datetime type, so a `DateTime(timezone=True)`
    # column round-trips as naive on read even though it was written aware —
    # comparing that against an aware `now()` raises. Postgres does not have
    # this quirk, but the read has to be correct on both.
    expires_at = row.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at is None or datetime.now(UTC) < expires_at:
        return row.access_token
    if provider not in REFRESHABLE or not row.refresh_token:
        return row.access_token
    fresh = await _refresh(cfg, provider, row.refresh_token)
    await save_token(db, provider, fresh)
    return str(fresh["access_token"])
