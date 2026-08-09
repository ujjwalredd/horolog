"""OAuth token exchange/storage and the calendar/tracker syncs built on it."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio

_tmpdir = tempfile.mkdtemp()
os.environ["HOROLOG_DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmpdir}/oauth.db"

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from horolog import oauth
from horolog.api import app
from horolog.db import OAuthTokenRow, init_db, session
from horolog.integrations import github, todoist
from horolog.integrations.google_calendar import GoogleCalendarProvider
from horolog.integrations.outlook_calendar import OutlookCalendarProvider
from horolog.settings import settings


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        for item in (await http.get("/api/intents")).json():
            await http.delete(f"/api/intents/{item['id']}")
        await http.put("/api/busy", json=[])
        for provider in oauth.PROVIDERS:
            await http.delete(f"/api/connections/{provider}")
        yield http


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """A session for tests that reach `oauth.py` directly — there is no HTTP
    endpoint for seeding a stored token before the request under test.

    Closed deterministically via `aclosing` rather than left for whichever
    happens first: garbage collection racing a later `async with` on the same
    session is exactly what threw `IllegalStateChangeError` here originally.
    """
    gen = cast("AsyncGenerator[AsyncSession, None]", session())
    try:
        yield await anext(gen)
    finally:
        await gen.aclose()


@pytest.fixture
def mock_http(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], None]:
    """Route every outbound `httpx.AsyncClient` call in the app to `handler`.

    A factory, not a shared client: application code opens its own
    `AsyncClient` per call, and httpx refuses to reuse one that already closed.
    """
    real = httpx.AsyncClient

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        monkeypatch.setattr(
            httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler))
        )

    return install


@pytest.fixture
def with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A client id/secret configured for every provider, so the OAuth routes
    take the real path instead of the credentials-missing shortcut."""
    cfg = settings()
    for provider in oauth.PROVIDERS:
        monkeypatch.setattr(cfg, f"{provider}_client_id", f"{provider}-id")
        monkeypatch.setattr(cfg, f"{provider}_client_secret", f"{provider}-secret")


# --------------------------------------------------------------------- state


def test_a_state_is_valid_exactly_once() -> None:
    token = oauth.new_state()
    assert oauth.consume_state(token) is True
    assert oauth.consume_state(token) is False, "a replayed state must not validate twice"


def test_an_unknown_state_is_rejected() -> None:
    assert oauth.consume_state("never-issued") is False


def test_an_expired_state_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = oauth.new_state()
    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + oauth._STATE_TTL_S + 1)
    assert oauth.consume_state(token) is False


# --------------------------------------------------------------- auth routes


@pytest.mark.asyncio
async def test_missing_credentials_redirect_home_honestly(client: AsyncClient) -> None:
    """No client id configured must say so - not fabricate a connection."""
    response = await client.get("/api/auth/google", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "status=credentials_missing" in location
    assert "provider=google" in location
    assert "token=" not in location


@pytest.mark.asyncio
async def test_configured_provider_redirects_to_the_real_consent_screen(
    client: AsyncClient, with_credentials: None
) -> None:
    response = await client.get("/api/auth/linear", follow_redirects=False)
    location = response.headers["location"]
    assert location.startswith("https://linear.app/oauth/authorize")
    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == ["linear-id"]
    assert query["redirect_uri"] == [f"{settings().public_api_url}/api/auth/callback/linear"]
    state = query["state"][0]
    assert oauth.consume_state(state), "the state in the redirect must be one the server issued"


@pytest.mark.asyncio
async def test_callback_without_a_valid_state_is_rejected(
    client: AsyncClient, with_credentials: None, db: AsyncSession
) -> None:
    response = await client.get(
        "/api/auth/callback/github?code=abc&state=forged", follow_redirects=False
    )
    location = response.headers["location"]
    assert "status=error" in location
    assert not await oauth.connected_providers(db)


@pytest.mark.asyncio
async def test_successful_callback_stores_the_token_server_side_only(
    client: AsyncClient, with_credentials: None, mock_http: Callable[..., None]
) -> None:
    """The whole point of storing tokens server-side: the redirect back to the
    browser must carry a status, never the access token itself."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "github.com"
        return httpx.Response(200, json={"access_token": "gho_realtoken", "scope": "repo"})

    mock_http(handler)
    state = oauth.new_state()
    response = await client.get(
        f"/api/auth/callback/github?code=abc123&state={state}", follow_redirects=False
    )
    location = response.headers["location"]
    assert "status=success" in location
    assert "provider=github" in location
    assert "gho_realtoken" not in location, "the access token must never reach the browser"

    connected = await client.get("/api/connections")
    assert connected.json()["github"] is True


@pytest.mark.asyncio
async def test_provider_rejection_surfaces_as_an_error_redirect(
    client: AsyncClient, with_credentials: None, mock_http: Callable[..., None]
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad_verification_code"})

    mock_http(handler)
    state = oauth.new_state()
    response = await client.get(
        f"/api/auth/callback/todoist?code=bad&state={state}", follow_redirects=False
    )
    assert "status=error" in response.headers["location"]


@pytest.mark.asyncio
async def test_provider_error_cannot_inject_extra_query_params(client: AsyncClient) -> None:
    """`error` comes straight from the callback query string - anyone can hit
    this endpoint directly with any value, not only a real provider. Building
    the redirect with an f-string let a crafted value break out of `error`'s
    slot and add parameters of its own to the URL the browser lands on."""
    payload = "hi&status=success&provider=google"
    response = await client.get(
        "/api/auth/callback/google", params={"error": payload}, follow_redirects=False
    )
    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert query["error"] == ["hi&status=success&provider=google"], (
        "the whole value must stay inside the error parameter, not become new ones"
    )
    assert query["status"] == ["error"], "an injected status must not override the real one"


@pytest.mark.asyncio
async def test_disconnect_forgets_the_token(
    client: AsyncClient, with_credentials: None, db: AsyncSession
) -> None:
    await oauth.save_token(db, "linear", {"access_token": "x"})
    assert (await client.get("/api/connections")).json()["linear"] is True

    removed = await client.delete("/api/connections/linear")
    assert removed.status_code == 204
    assert (await client.get("/api/connections")).json()["linear"] is False


# --------------------------------------------------------------- token refresh


@pytest.mark.asyncio
async def test_an_unexpired_token_is_returned_without_refreshing(db: AsyncSession) -> None:
    await oauth.save_token(db, "google", {"access_token": "still-good", "expires_in": 3600})
    token = await oauth.valid_access_token(db, settings(), "google")
    assert token == "still-good"


@pytest.mark.asyncio
async def test_an_expired_refreshable_token_is_refreshed_transparently(
    mock_http: Callable[..., None], db: AsyncSession
) -> None:
    await oauth.save_token(
        db, "google", {"access_token": "stale", "refresh_token": "r1", "expires_in": -10}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "oauth2.googleapis.com"
        return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600})

    mock_http(handler)
    token = await oauth.valid_access_token(db, settings(), "google")
    assert token == "fresh"


@pytest.mark.asyncio
async def test_refresh_keeps_the_old_refresh_token_when_none_is_reissued(
    mock_http: Callable[..., None], db: AsyncSession
) -> None:
    """Google only hands back a refresh_token on first consent - a refresh
    response that omits one must not erase the one already stored."""
    await oauth.save_token(
        db, "google", {"access_token": "stale", "refresh_token": "keep-me", "expires_in": -10}
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600})

    mock_http(handler)
    await oauth.valid_access_token(db, settings(), "google")
    row = await db.get(OAuthTokenRow, "google")
    assert row is not None and row.refresh_token == "keep-me"


@pytest.mark.asyncio
async def test_non_refreshable_providers_hand_back_their_token_even_when_stale(
    db: AsyncSession,
) -> None:
    """GitHub/Todoist/Linear tokens issued via OAuth do not expire under
    normal use - there is nothing to refresh them against."""
    await oauth.save_token(db, "github", {"access_token": "still-fine"})
    token = await oauth.valid_access_token(db, settings(), "github")
    assert token == "still-fine"


# ------------------------------------------------------------------ github


@pytest.mark.asyncio
async def test_github_pull_requests_are_not_scheduled_as_tasks(
    mock_http: Callable[..., None],
) -> None:
    body = [
        {"id": 1, "number": 10, "title": "A real issue"},
        {"id": 2, "number": 11, "title": "A PR", "pull_request": {}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer ghp_x"
        return httpx.Response(200, json=body)

    mock_http(handler)
    issues = await github.fetch_github_issues("ghp_x")
    assert [i.number for i in issues] == [10]


@pytest.mark.asyncio
async def test_github_sync_creates_placeable_intents(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    """The original integration constructed `Intent(splittable=True)`, a field
    that does not exist, so every issue raised on import. This is the
    regression test for that bug staying fixed."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 5, "number": 42, "title": "Fix the flaky test"}])

    mock_http(handler)
    synced = await client.post("/api/sync/github", json={"token": "ghp_x"})
    assert synced.status_code == 200
    assert synced.json()["issues"] == 1

    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["blocks"] if "#42" in b["title"]], (
        "an imported issue must actually be placeable, not just stored"
    )


@pytest.mark.asyncio
async def test_github_sync_without_a_token_or_connection_is_refused(client: AsyncClient) -> None:
    refused = await client.post("/api/sync/github", json={"token": ""})
    assert refused.status_code == 409


# ------------------------------------------------------------------ todoist


@pytest.mark.asyncio
async def test_todoist_completed_and_blank_tasks_are_dropped(
    mock_http: Callable[..., None],
) -> None:
    body = [
        {"id": "1", "content": "Ship it", "priority": 4},
        {"id": "2", "content": "Done already", "is_completed": True},
        {"id": "3", "content": "  ", "priority": 1},
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    mock_http(handler)
    tasks = await todoist.fetch_todoist_tasks("tok")
    assert [t.content for t in tasks] == ["Ship it"]
    assert tasks[0].priority.name == "P1", "todoist priority 4 (urgent) must map to Horolog P1"


@pytest.mark.asyncio
async def test_todoist_sync_creates_placeable_intents(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "9", "content": "Write the doc", "priority": 3}])

    mock_http(handler)
    synced = await client.post("/api/sync/todoist", json={"token": "tok"})
    assert synced.status_code == 200
    assert synced.json()["tasks"] == 1
    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["blocks"] if "Write the doc" in b["title"]]


@pytest.mark.asyncio
async def test_todoist_falls_back_to_a_stored_oauth_connection(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession
) -> None:
    """A pasted key is optional: an OAuth-connected account must sync with an
    empty body, not demand the user paste a key it already has."""
    await oauth.save_token(db, "todoist", {"access_token": "from-oauth"})

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=[])

    mock_http(handler)
    synced = await client.post("/api/sync/todoist", json={"token": ""})
    assert synced.status_code == 200
    assert seen["auth"] == "Bearer from-oauth"


# --------------------------------------------------------------- calendars


@pytest.mark.asyncio
async def test_google_calendar_skips_cancelled_and_transparent_events(
    mock_http: Callable[..., None],
) -> None:
    body = {
        "items": [
            {
                "id": "a",
                "summary": "Real meeting",
                "status": "confirmed",
                "start": {"dateTime": "2026-08-10T14:00:00-04:00"},
                "end": {"dateTime": "2026-08-10T15:00:00-04:00"},
            },
            {
                "id": "b",
                "summary": "Cancelled",
                "status": "cancelled",
                "start": {"dateTime": "2026-08-10T16:00:00-04:00"},
                "end": {"dateTime": "2026-08-10T17:00:00-04:00"},
            },
            {
                "id": "c",
                "summary": "Marked free",
                "status": "confirmed",
                "transparency": "transparent",
                "start": {"dateTime": "2026-08-10T18:00:00-04:00"},
                "end": {"dateTime": "2026-08-10T19:00:00-04:00"},
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json=body)

    mock_http(handler)
    from zoneinfo import ZoneInfo

    provider = GoogleCalendarProvider("tok", ZoneInfo("America/New_York"))
    base = datetime(2026, 8, 10, tzinfo=ZoneInfo("America/New_York"))
    events = await provider.fetch(base, 7)
    assert [e.label for e in events] == ["Real meeting"]


@pytest.mark.asyncio
async def test_outlook_calendar_skips_free_and_cancelled_events(
    mock_http: Callable[..., None],
) -> None:
    body = {
        "value": [
            {
                "id": "a",
                "subject": "Real meeting",
                "showAs": "busy",
                "start": {"dateTime": "2026-08-10T18:00:00.0000000"},
                "end": {"dateTime": "2026-08-10T19:00:00.0000000"},
            },
            {
                "id": "b",
                "subject": "Free block",
                "showAs": "free",
                "start": {"dateTime": "2026-08-10T20:00:00.0000000"},
                "end": {"dateTime": "2026-08-10T21:00:00.0000000"},
            },
            {
                "id": "c",
                "subject": "Cancelled",
                "isCancelled": True,
                "showAs": "busy",
                "start": {"dateTime": "2026-08-10T22:00:00.0000000"},
                "end": {"dateTime": "2026-08-10T23:00:00.0000000"},
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json=body)

    mock_http(handler)
    from zoneinfo import ZoneInfo

    provider = OutlookCalendarProvider("tok", ZoneInfo("UTC"))
    base = datetime(2026, 8, 10, tzinfo=ZoneInfo("UTC"))
    events = await provider.fetch(base, 7)
    assert [e.label for e in events] == ["Real meeting"]


@pytest.mark.asyncio
async def test_google_sync_requires_a_connection(client: AsyncClient) -> None:
    refused = await client.post("/api/sync/google")
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_google_sync_mirrors_real_events_into_busy(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession
) -> None:
    await oauth.save_token(db, "google", {"access_token": "tok"})

    base_day = datetime.now(UTC) + timedelta(days=1)
    body = {
        "items": [
            {
                "id": "z",
                "summary": "Board meeting",
                "status": "confirmed",
                "start": {"dateTime": base_day.replace(hour=14, minute=0).isoformat()},
                "end": {"dateTime": base_day.replace(hour=15, minute=0).isoformat()},
            }
        ]
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    mock_http(handler)
    synced = await client.post("/api/sync/google")
    assert synced.status_code == 200
    assert synced.json()["events"] == 1

    plan = (await client.get("/api/plan")).json()
    assert any(b["source"] == "google" and "Board meeting" in b["label"] for b in plan["busy"])
