"""OAuth token exchange/storage and the calendar/tracker syncs built on it."""

from __future__ import annotations

import base64
import json
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
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from horolog import oauth
from horolog.api import _push_calendar, app
from horolog.db import BusyRow, OAuthTokenRow, SyncedBlockRow, init_db, session
from horolog.integrations import clickup, github, jira, notion, todoist
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
        # `PUT /api/busy` with an empty body only clears the "manual" source
        # by design — each sync source is an independent mirror, so syncing
        # one must never wipe another (see `replace_busy`'s own docstring).
        # That's correct in production, but `db.py`'s `_engine`/`settings`
        # are process-wide `@lru_cache`s: when the full suite runs in one
        # pytest process, whichever test file's database happens to be
        # touched first wins, and every other file's tests silently share
        # that one file — so a "booking"-sourced busy row left behind by
        # test_integrations.py's booking tests can land in this file's
        # tests too. Same reasoning as the `synced_blocks` cleanup below:
        # no HTTP route clears every source at once, so it needs its own.
        gen = cast("AsyncGenerator[AsyncSession, None]", session())
        db = await anext(gen)
        await db.execute(delete(BusyRow))
        await db.execute(delete(SyncedBlockRow))
        await db.commit()
        await gen.aclose()
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


@pytest.mark.asyncio
async def test_pasted_token_whitespace_is_stripped_before_use(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    """A key copied from a terminal or text field routinely carries a
    trailing newline or space. Left in, `Authorization: Bearer <key> ` is a
    header value httpx's own validation rejects outright — a crash a user
    would see as a broken sync button, not a bad paste. Regression test."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=[])

    mock_http(handler)
    synced = await client.post("/api/sync/todoist", json={"token": "  tok\n"})
    assert synced.status_code == 200
    assert seen["auth"] == "Bearer tok"


@pytest.mark.asyncio
async def test_pasted_token_whitespace_only_falls_back_to_oauth(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession
) -> None:
    """A whitespace-only paste (an empty field plus a stray space) must be
    treated as no paste at all, not as a real — and then invalid — key."""
    await oauth.save_token(db, "todoist", {"access_token": "from-oauth"})
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=[])

    mock_http(handler)
    synced = await client.post("/api/sync/todoist", json={"token": "   "})
    assert synced.status_code == 200
    assert seen["auth"] == "Bearer from-oauth"


# -------------------------------------------------------------------- notion


@pytest.mark.asyncio
async def test_notion_rejects_a_malformed_credential() -> None:
    with pytest.raises(notion.NotionError):
        await notion.fetch_notion_tasks("no-colon-here")


@pytest.mark.asyncio
async def test_notion_untitled_pages_are_dropped(mock_http: Callable[..., None]) -> None:
    body = {
        "results": [
            {
                "id": "1",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Write the doc"}]}
                },
            },
            {"id": "2", "properties": {"Name": {"type": "title", "title": []}}},
        ]
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    mock_http(handler)
    tasks = await notion.fetch_notion_tasks("db123:secret")
    assert [t.title for t in tasks] == ["Write the doc"]


@pytest.mark.asyncio
async def test_notion_sync_creates_placeable_intents(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    body = {
        "results": [
            {
                "id": "1",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Ship the feature"}]}
                },
            }
        ]
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    mock_http(handler)
    synced = await client.post("/api/sync/notion", json={"token": "db123:secret"})
    assert synced.status_code == 200
    assert synced.json()["tasks"] == 1
    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["blocks"] if "Ship the feature" in b["title"]]


@pytest.mark.asyncio
async def test_notion_sync_follows_pagination(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    """A database with more rows than fit on one page must not silently
    truncate — this is the regression test for that bug."""
    pages = {
        None: {
            "results": [
                {
                    "id": "1",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "First page"}]}
                    },
                }
            ],
            "has_more": True,
            "next_cursor": "cursor-2",
        },
        "cursor-2": {
            "results": [
                {
                    "id": "2",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Second page"}]}
                    },
                }
            ],
            "has_more": False,
            "next_cursor": None,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        return httpx.Response(200, json=pages[body.get("start_cursor")])

    mock_http(handler)
    tasks = await notion.fetch_notion_tasks("db123:secret")
    assert [t.title for t in tasks] == ["First page", "Second page"]


@pytest.mark.asyncio
async def test_notion_sync_without_a_credential_is_refused(client: AsyncClient) -> None:
    """No OAuth app exists for Notion — an empty body must be a clear 422,
    never a 409 implying a "Connect" button that isn't rendered."""
    response = await client.post("/api/sync/notion", json={"token": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_notion_sync_whitespace_only_credential_is_refused(client: AsyncClient) -> None:
    """A whitespace-only paste must be refused the same as an empty one, not
    passed through to a crashing header value. Regression test — this key-
    only path uses a different helper than the OAuth-capable trackers'."""
    response = await client.post("/api/sync/notion", json={"token": "   "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_notion_sync_credential_whitespace_is_stripped(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"results": []})

    mock_http(handler)
    synced = await client.post("/api/sync/notion", json={"token": "  db123:secret\n"})
    assert synced.status_code == 200
    assert seen["auth"] == "Bearer secret"


# ------------------------------------------------------------------- clickup


@pytest.mark.asyncio
async def test_clickup_rejects_a_malformed_credential() -> None:
    with pytest.raises(clickup.ClickUpError):
        await clickup.fetch_clickup_tasks("no-colon-here")


@pytest.mark.asyncio
async def test_clickup_only_the_token_owners_tasks_are_requested(
    mock_http: Callable[..., None],
) -> None:
    """A team's /task endpoint returns everyone's tasks unless explicitly
    filtered to the token owner — this pins that the owner is resolved via
    /user first and threaded into the assignees[] filter, not skipped."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user"):
            return httpx.Response(200, json={"user": {"id": 42}})
        assert request.url.params["assignees[]"] == "42"
        return httpx.Response(
            200, json={"tasks": [{"id": "1", "name": "Fix the bug", "priority": {"id": "2"}}]}
        )

    mock_http(handler)
    tasks = await clickup.fetch_clickup_tasks("team1:tok")
    assert [t.name for t in tasks] == ["Fix the bug"]
    assert tasks[0].priority.name == "P2"


@pytest.mark.asyncio
async def test_clickup_sync_creates_placeable_intents(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user"):
            return httpx.Response(200, json={"user": {"id": 42}})
        return httpx.Response(200, json={"tasks": [{"id": "1", "name": "Fix the bug"}]})

    mock_http(handler)
    synced = await client.post("/api/sync/clickup", json={"token": "team1:tok"})
    assert synced.status_code == 200
    assert synced.json()["tasks"] == 1
    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["blocks"] if "Fix the bug" in b["title"]]


@pytest.mark.asyncio
async def test_clickup_sync_follows_pagination(mock_http: Callable[..., None]) -> None:
    """A full first page (100 tasks, ClickUp's own page size) must not be
    mistaken for the end of the list — this is the regression test."""
    first_page = [{"id": str(i), "name": f"Task {i}"} for i in range(100)]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user"):
            return httpx.Response(200, json={"user": {"id": 42}})
        page = request.url.params["page"]
        if page == "0":
            return httpx.Response(200, json={"tasks": first_page})
        return httpx.Response(200, json={"tasks": [{"id": "100", "name": "Task 100"}]})

    mock_http(handler)
    tasks = await clickup.fetch_clickup_tasks("team1:tok")
    assert len(tasks) == 101
    assert tasks[-1].name == "Task 100"


@pytest.mark.asyncio
async def test_clickup_sync_without_a_credential_is_refused(client: AsyncClient) -> None:
    response = await client.post("/api/sync/clickup", json={"token": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------- jira


@pytest.mark.asyncio
async def test_jira_rejects_a_malformed_credential() -> None:
    with pytest.raises(jira.JiraError):
        await jira.fetch_jira_issues("only:two-parts")


@pytest.mark.asyncio
async def test_jira_uses_basic_auth_built_from_the_pasted_credential(
    mock_http: Callable[..., None],
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "id": "10001",
                        "key": "ENG-1",
                        "fields": {"summary": "Fix the login bug", "priority": {"name": "High"}},
                    }
                ]
            },
        )

    mock_http(handler)
    issues = await jira.fetch_jira_issues("mysite:me@example.com:tok")
    expected = base64.b64encode(b"me@example.com:tok").decode()
    assert seen["auth"] == f"Basic {expected}"
    assert [i.summary for i in issues] == ["Fix the login bug"]
    assert issues[0].priority.name == "P2"


@pytest.mark.asyncio
async def test_jira_sync_creates_placeable_intents(
    client: AsyncClient, mock_http: Callable[..., None]
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"issues": [{"id": "1", "key": "ENG-1", "fields": {"summary": "Fix it"}}]}
        )

    mock_http(handler)
    synced = await client.post("/api/sync/jira", json={"token": "site:me@example.com:tok"})
    assert synced.status_code == 200
    assert synced.json()["issues"] == 1
    plan = (await client.get("/api/plan")).json()
    assert [b for b in plan["blocks"] if "Fix it" in b["title"]]


@pytest.mark.asyncio
async def test_jira_sync_follows_pagination(mock_http: Callable[..., None]) -> None:
    """`total` says more issues exist past this page — startAt must advance
    to fetch them, not stop at the first response. Regression test."""

    def handler(request: httpx.Request) -> httpx.Response:
        start_at = int(request.url.params["startAt"])
        if start_at == 0:
            return httpx.Response(
                200,
                json={
                    "startAt": 0,
                    "total": 2,
                    "issues": [{"id": "1", "key": "ENG-1", "fields": {"summary": "First"}}],
                },
            )
        return httpx.Response(
            200,
            json={
                "startAt": 1,
                "total": 2,
                "issues": [{"id": "2", "key": "ENG-2", "fields": {"summary": "Second"}}],
            },
        )

    mock_http(handler)
    issues = await jira.fetch_jira_issues("site:me@example.com:tok")
    assert [i.summary for i in issues] == ["First", "Second"]


@pytest.mark.asyncio
async def test_jira_sync_without_a_credential_is_refused(client: AsyncClient) -> None:
    response = await client.post("/api/sync/jira", json={"token": ""})
    assert response.status_code == 422


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


# --------------------------------------------------------------- background sync


@pytest.mark.asyncio
async def test_background_sync_is_a_noop_with_nothing_connected(db: AsyncSession) -> None:
    from horolog.api import _sync_connected_calendars

    await _sync_connected_calendars(db)  # must not raise


@pytest.mark.asyncio
async def test_background_sync_skips_a_failed_provider_without_stopping_the_next(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession
) -> None:
    """One provider's outage must not stop the loop from reaching the other,
    and must not propagate out of the tick that runs it."""
    from horolog.api import _sync_connected_calendars

    await oauth.save_token(db, "google", {"access_token": "tok"})
    await oauth.save_token(db, "outlook", {"access_token": "tok"})

    base_day = datetime.now(UTC) + timedelta(days=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if "googleapis.com" in str(request.url):
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "o1",
                        "subject": "1:1",
                        "showAs": "busy",
                        "isCancelled": False,
                        "start": {"dateTime": base_day.replace(hour=10, minute=0).isoformat()},
                        "end": {"dateTime": base_day.replace(hour=10, minute=30).isoformat()},
                    }
                ]
            },
        )

    mock_http(handler)
    await _sync_connected_calendars(db)  # google 500s; must not raise

    plan = (await client.get("/api/plan")).json()
    assert any(b["source"] == "outlook" and "1:1" in b["label"] for b in plan["busy"]), (
        "outlook must still sync even though google failed in the same tick"
    )


# --------------------------------------------------------------- calendar push (write-back)


@pytest.mark.asyncio
async def test_google_fetch_follows_pagination(mock_http: Callable[..., None]) -> None:
    """A dense window past one page must not silently truncate — the same bug
    class fixed for the tracker integrations in `ae2bd11`."""
    from zoneinfo import ZoneInfo

    pages = {
        None: {
            "items": [
                {
                    "id": "a",
                    "summary": "Page one",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-08-10T14:00:00-04:00"},
                    "end": {"dateTime": "2026-08-10T15:00:00-04:00"},
                }
            ],
            "nextPageToken": "p2",
        },
        "p2": {
            "items": [
                {
                    "id": "b",
                    "summary": "Page two",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-08-11T14:00:00-04:00"},
                    "end": {"dateTime": "2026-08-11T15:00:00-04:00"},
                }
            ],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        return httpx.Response(200, json=pages[token])

    mock_http(handler)
    provider = GoogleCalendarProvider("tok", ZoneInfo("America/New_York"))
    base = datetime(2026, 8, 10, tzinfo=ZoneInfo("America/New_York"))
    events = await provider.fetch(base, 7)
    assert {e.label for e in events} == {"Page one", "Page two"}


@pytest.mark.asyncio
async def test_outlook_fetch_follows_pagination(mock_http: Callable[..., None]) -> None:
    from zoneinfo import ZoneInfo

    second_page = {
        "value": [
            {
                "id": "b",
                "subject": "Page two",
                "showAs": "busy",
                "start": {"dateTime": "2026-08-11T18:00:00.0000000"},
                "end": {"dateTime": "2026-08-11T19:00:00.0000000"},
            }
        ]
    }
    first_page = {
        "value": [
            {
                "id": "a",
                "subject": "Page one",
                "showAs": "busy",
                "start": {"dateTime": "2026-08-10T18:00:00.0000000"},
                "end": {"dateTime": "2026-08-10T19:00:00.0000000"},
            }
        ],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/calendarview?$skip=1",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=second_page if "$skip" in str(request.url) else first_page)

    mock_http(handler)
    provider = OutlookCalendarProvider("tok", ZoneInfo("UTC"))
    base = datetime(2026, 8, 10, tzinfo=ZoneInfo("UTC"))
    events = await provider.fetch(base, 7)
    assert {e.label for e in events} == {"Page one", "Page two"}


class _FakeGoogleBackend:
    """A minimal in-memory stand-in for the parts of the Calendar API the
    writer touches: a calendar list/create, and per-calendar event
    create/patch/delete. State persists across calls within one test, the
    same way a real account would, so a diff-based push can be exercised
    across multiple `_push_calendar` calls rather than one request at a time.
    """

    def __init__(self) -> None:
        self.calendars: dict[str, str] = {}
        self.events: dict[str, dict[str, dict[str, object]]] = {"primary": {}}
        self.calls: list[tuple[str, str]] = []
        self._n = 0

    def _next_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        body = json.loads(request.content) if request.content else {}

        if path == "/calendar/v3/users/me/calendarList" and method == "GET":
            items = [{"id": cid, "summary": name} for cid, name in self.calendars.items()]
            return httpx.Response(200, json={"items": items})
        if path == "/calendar/v3/calendars" and method == "POST":
            cid = self._next_id("cal")
            self.calendars[cid] = body["summary"]
            self.events[cid] = {}
            return httpx.Response(200, json={"id": cid})
        if path == "/calendar/v3/calendars/primary/events" and method == "GET":
            return httpx.Response(200, json={"items": list(self.events["primary"].values())})

        parts = path.split("/")
        if len(parts) >= 6 and parts[3] == "calendars" and parts[5] == "events":
            cid = parts[4]
            if len(parts) == 6 and method == "POST":
                eid = self._next_id("evt")
                self.events.setdefault(cid, {})[eid] = {"id": eid, **body}
                return httpx.Response(200, json={"id": eid})
            if len(parts) == 7:
                eid = parts[6]
                if method == "PATCH":
                    if eid not in self.events.get(cid, {}):
                        return httpx.Response(404, json={})
                    self.events[cid][eid].update(body)
                    return httpx.Response(200, json={"id": eid})
                if method == "DELETE":
                    if eid not in self.events.get(cid, {}):
                        return httpx.Response(404, json={})
                    del self.events[cid][eid]
                    return httpx.Response(204)
        return httpx.Response(404, json={"error": f"unhandled {method} {path}"})


@pytest_asyncio.fixture
async def with_writeback(monkeypatch: pytest.MonkeyPatch, db: AsyncSession) -> None:
    monkeypatch.setattr(settings(), "calendar_writeback_enabled", True)
    await oauth.save_token(db, "google", {"access_token": "tok"})


@pytest.mark.asyncio
async def test_calendar_push_requires_a_connection(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings(), "calendar_writeback_enabled", True)
    refused = await client.post("/api/calendar/push", json={"provider": "google"})
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_calendar_push_is_disabled_by_default(client: AsyncClient, db: AsyncSession) -> None:
    await oauth.save_token(db, "google", {"access_token": "tok"})
    refused = await client.post("/api/calendar/push", json={"provider": "google"})
    assert refused.status_code == 409
    assert "disabled" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_calendar_push_creates_one_event_per_block(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession, with_writeback: None
) -> None:
    await client.post("/api/intents", json={"title": "Write it back", "minutes_per_period": 60})

    backend = _FakeGoogleBackend()
    mock_http(backend.handle)
    result = await _push_calendar(db, "google")
    assert result == {"created": 1, "moved": 0, "removed": 0}

    [calendar_id] = backend.calendars
    assert backend.calendars[calendar_id] == "Horolog"
    [event] = backend.events[calendar_id].values()
    assert event["summary"] == "Write it back"

    rows = (await db.execute(select(SyncedBlockRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_id == event["id"]


@pytest.mark.asyncio
async def test_calendar_push_twice_with_nothing_changed_is_a_noop(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession, with_writeback: None
) -> None:
    """The write-back mirror of the read side's 're-plan with nothing changed
    is a provable no-op': a second push must issue no create/patch/delete."""
    await client.post("/api/intents", json={"title": "Steady", "minutes_per_period": 60})

    backend = _FakeGoogleBackend()
    mock_http(backend.handle)
    await _push_calendar(db, "google")
    calls_before = len(backend.calls)

    result = await _push_calendar(db, "google")
    assert result == {"created": 0, "moved": 0, "removed": 0}
    new_calls = backend.calls[calls_before:]
    assert all(method == "GET" for method, _ in new_calls), (
        f"a no-op push must only resolve the calendar, not write: {new_calls}"
    )


@pytest.mark.asyncio
async def test_calendar_push_moves_only_the_block_that_actually_shifted(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession, with_writeback: None
) -> None:
    """Two intents pushed, then a real collision forces a re-solve that moves
    one of them — the diff must PATCH exactly that one event and leave the
    other untouched, the write-side version of the two-pass placer's
    'only the blocks actually hit move' guarantee."""
    a = (
        await client.post(
            "/api/intents",
            json={
                "title": "Anchor",
                "minutes_per_period": 60,
                "min_chunk_minutes": 60,
                "max_chunk_minutes": 60,
                "window_start_min": 540,
                "window_end_min": 600,
            },
        )
    ).json()
    b = (
        await client.post(
            "/api/intents",
            json={
                "title": "Mover",
                "minutes_per_period": 60,
                "min_chunk_minutes": 60,
                "max_chunk_minutes": 60,
                "window_start_min": 600,
                "window_end_min": 720,
            },
        )
    ).json()

    backend = _FakeGoogleBackend()
    mock_http(backend.handle)
    await _push_calendar(db, "google")
    [calendar_id] = backend.calendars
    assert len(backend.events[calendar_id]) == 2
    event_ids_before = {eid: e["start"] for eid, e in backend.events[calendar_id].items()}

    # A real meeting lands directly on "Mover"'s only legal window, so a
    # re-solve has to relocate it while "Anchor" — untouched — stays put.
    plan_before = await client.get("/api/plan")
    origin_iso = plan_before.json()["origin"]
    base = datetime.fromisoformat(origin_iso)
    await client.put(
        "/api/busy",
        json=[
            {
                "label": "Surprise meeting",
                "start": (base + timedelta(hours=10)).isoformat(),
                "end": (base + timedelta(hours=11)).isoformat(),
            }
        ],
    )

    result = await _push_calendar(db, "google")
    assert result["moved"] == 1
    assert result["created"] == 0
    assert result["removed"] == 0

    events_after = backend.events[calendar_id]
    assert len(events_after) == 2, "the moved block is patched in place, not deleted and recreated"
    unchanged = [eid for eid, e in events_after.items() if e["start"] == event_ids_before.get(eid)]
    assert len(unchanged) == 1, "exactly one of the two events must have kept its original time"

    for intent in (a, b):
        assert intent  # created successfully above


@pytest.mark.asyncio
async def test_calendar_push_deletes_the_event_for_a_removed_intent(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession, with_writeback: None
) -> None:
    created = (
        await client.post("/api/intents", json={"title": "Temporary", "minutes_per_period": 60})
    ).json()

    backend = _FakeGoogleBackend()
    mock_http(backend.handle)
    await _push_calendar(db, "google")
    [calendar_id] = backend.calendars
    assert len(backend.events[calendar_id]) == 1

    await client.delete(f"/api/intents/{created['id']}")
    result = await _push_calendar(db, "google")
    assert result == {"created": 0, "moved": 0, "removed": 1}
    assert backend.events[calendar_id] == {}
    rows = (await db.execute(select(SyncedBlockRow))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_calendar_push_never_leaks_its_own_events_back_as_busy_time(
    client: AsyncClient, mock_http: Callable[..., None], db: AsyncSession, with_writeback: None
) -> None:
    """The whole reason write-back targets a secondary calendar: events it
    creates must never come back through `fetch` (which reads only
    `calendars/primary/events`) as busy time the solver then schedules
    around, or the app would eat its own tail."""
    await client.post("/api/intents", json={"title": "Self-contained", "minutes_per_period": 60})

    backend = _FakeGoogleBackend()
    mock_http(backend.handle)
    await _push_calendar(db, "google")
    [calendar_id] = backend.calendars
    assert len(backend.events[calendar_id]) == 1
    assert backend.events["primary"] == {}, "the writer must never touch the primary calendar"

    synced = await client.post("/api/sync/google")
    assert synced.json()["events"] == 0


@pytest.mark.asyncio
async def test_calendar_push_surfaces_a_reconnect_message_on_scope_rejection(
    client: AsyncClient, mock_http: Callable[..., None], with_writeback: None
) -> None:
    """An old, read-only-scoped token must fail with an actionable message,
    not a bare 500 — this is what a user upgrading past the 0.2.0 scope
    change actually sees before reconnecting."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "insufficient scope"})

    mock_http(handler)
    response = await client.post("/api/calendar/push", json={"provider": "google"})
    assert response.status_code == 502
    assert "reconnect" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_calendar_push_unknown_provider_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings(), "calendar_writeback_enabled", True)
    response = await client.post("/api/calendar/push", json={"provider": "notacalendar"})
    assert response.status_code == 404
