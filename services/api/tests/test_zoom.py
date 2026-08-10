"""Zoom auto-creation on Smart Meetings, and best-effort cleanup on delete —
both against a mocked Zoom, never a live account.

The one property worth pinning above all: a Zoom outage must never stop a
meeting from being scheduled. Every failure-path test here asserts 201 first,
then checks zoom_join_url separately.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Callable

import httpx
import pytest
import pytest_asyncio

_tmpdir = tempfile.mkdtemp()
os.environ["HOROLOG_DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmpdir}/zoom.db"

from httpx import ASGITransport, AsyncClient

from horolog.api import app
from horolog.db import init_db
from horolog.integrations import zoom as zoom_module
from horolog.settings import settings


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        for item in (await http.get("/api/intents")).json():
            await http.delete(f"/api/intents/{item['id']}")
        yield http


@pytest.fixture
def mock_http(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], None]:
    """Route every outbound `httpx.AsyncClient` call in the app to `handler`."""
    real = httpx.AsyncClient

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        monkeypatch.setattr(
            httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler))
        )

    return install


@pytest.fixture
def with_zoom_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # The token cache is a module-level dict keyed by account id, so it
    # outlives any one test — clear it, or a cached token from an earlier
    # test would silently skip the token exchange this test means to mock.
    zoom_module._token_cache.clear()
    cfg = settings()
    monkeypatch.setattr(cfg, "zoom_account_id", "acct-1")
    monkeypatch.setattr(cfg, "zoom_client_id", "client-1")
    monkeypatch.setattr(cfg, "zoom_client_secret", "secret-1")


def _meeting_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Weekly sync",
        "kind": "meeting",
        "priority": 2,
        "minutes_per_period": 30,
        "min_chunk_minutes": 30,
        "max_chunk_minutes": 30,
    }
    return {**base, **overrides}


def _zoom_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "zoom.us":
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    if request.method == "POST" and request.url.path == "/v2/users/me/meetings":
        return httpx.Response(201, json={"id": "999", "join_url": "https://zoom.us/j/999"})
    if request.method == "DELETE":
        return httpx.Response(204)
    raise AssertionError(f"unexpected request: {request.method} {request.url}")


@pytest.mark.asyncio
async def test_meeting_gets_a_zoom_link_when_configured(
    client: AsyncClient, mock_http: Callable[..., None], with_zoom_credentials: None
) -> None:
    mock_http(_zoom_handler)
    response = await client.post("/api/intents", json=_meeting_payload())
    assert response.status_code == 201
    assert response.json()["zoom_join_url"] == "https://zoom.us/j/999"
    assert response.json()["zoom_meeting_id"] == "999"


@pytest.mark.asyncio
async def test_meeting_has_no_zoom_link_when_unconfigured(client: AsyncClient) -> None:
    """The default for every existing user — zero behaviour change without
    HOROLOG_ZOOM_* set. No mock_http installed: if the code tried to reach
    Zoom anyway, this would hang or fail against a real network call."""
    response = await client.post("/api/intents", json=_meeting_payload())
    assert response.status_code == 201
    assert response.json()["zoom_join_url"] is None
    assert response.json()["zoom_meeting_id"] is None


@pytest.mark.asyncio
async def test_non_meeting_intents_never_call_zoom(
    client: AsyncClient, mock_http: Callable[..., None], with_zoom_credentials: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Zoom must not be called for a non-meeting intent: {request.url}")

    mock_http(handler)
    response = await client.post(
        "/api/intents",
        json={
            "title": "Deep work",
            "kind": "focus",
            "minutes_per_period": 120,
            "min_chunk_minutes": 90,
            "max_chunk_minutes": 120,
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_a_zoom_outage_never_blocks_scheduling(
    client: AsyncClient, mock_http: Callable[..., None], with_zoom_credentials: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "zoom.us":
            return httpx.Response(401, json={"reason": "bad credentials"})
        raise AssertionError("must not reach the meetings endpoint after a token failure")

    mock_http(handler)
    response = await client.post("/api/intents", json=_meeting_payload())
    assert response.status_code == 201, "a Zoom outage must not stop the meeting being scheduled"
    assert response.json()["zoom_join_url"] is None


@pytest.mark.asyncio
async def test_deleting_a_meeting_removes_its_zoom_meeting(
    client: AsyncClient, mock_http: Callable[..., None], with_zoom_credentials: None
) -> None:
    deleted_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "zoom.us":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if request.method == "POST":
            return httpx.Response(201, json={"id": "999", "join_url": "https://zoom.us/j/999"})
        if request.method == "DELETE":
            deleted_urls.append(str(request.url))
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    mock_http(handler)
    created = await client.post("/api/intents", json=_meeting_payload())
    intent_id = created.json()["id"]

    deleted = await client.delete(f"/api/intents/{intent_id}")
    assert deleted.status_code == 204
    assert any("/meetings/999" in url for url in deleted_urls)


@pytest.mark.asyncio
async def test_deleting_a_meeting_survives_zoom_being_unreachable(
    client: AsyncClient, mock_http: Callable[..., None], with_zoom_credentials: None
) -> None:
    """An orphaned Zoom meeting is an acceptable outcome; a delete that fails
    because Zoom is down is not."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "zoom.us":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if request.method == "POST":
            return httpx.Response(201, json={"id": "999", "join_url": "https://zoom.us/j/999"})
        raise httpx.ConnectError("Zoom is unreachable")

    mock_http(handler)
    created = await client.post("/api/intents", json=_meeting_payload())
    intent_id = created.json()["id"]

    deleted = await client.delete(f"/api/intents/{intent_id}")
    assert deleted.status_code == 204
