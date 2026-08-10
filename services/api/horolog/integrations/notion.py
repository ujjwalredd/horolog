"""Notion — pull every page in a database as schedulable work.

Notion databases have no fixed schema, so there is no universal "not done"
filter to build without per-user configuration Horolog has no UI for — every
page in the database is imported as-is. Point this at a database that only
holds active work, or filter it down in Notion itself before syncing.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

_API_VERSION = "2022-06-28"
DEFAULT_MINUTES = 45
"""Notion pages carry no standard duration property — most imported tasks
land on this default, same reasoning as todoist.py's."""


class NotionTask(BaseModel):
    """One database page, reduced to what the scheduler needs."""

    id: str
    title: str = Field(min_length=1)
    minutes: int = DEFAULT_MINUTES


class NotionError(RuntimeError):
    """Notion could not be read. Message is fit to show a user."""


def _title(page: dict[str, object]) -> str:
    """The value of whichever property has type "title" — every Notion
    database has exactly one, under a name the user chose themselves, so it
    cannot be looked up by a fixed key."""
    properties = page.get("properties")
    if not isinstance(properties, dict):
        return ""
    for prop in properties.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            parts = prop.get("title")
            if isinstance(parts, list):
                return "".join(
                    str(part.get("plain_text", "")) for part in parts if isinstance(part, dict)
                ).strip()
    return ""


async def fetch_notion_tasks(credential: str, timeout: float = 30.0) -> list[NotionTask]:
    """Every page in the database, from a pasted `database_id:integration_token`.

    Notion has no per-request "who is this token for" concept the way a
    bearer-only API does — the database id has to travel with the token, so
    the two are pasted together rather than widening the shared paste-a-key
    UI for one provider.
    """
    database_id, _, token = credential.partition(":")
    if not database_id or not token:
        raise NotionError("expected database_id:integration_token")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers={"Authorization": f"Bearer {token}", "Notion-Version": _API_VERSION},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise NotionError(f"could not reach Notion: {exc}") from exc
    except ValueError as exc:
        raise NotionError("Notion returned something that was not JSON") from exc

    tasks: list[NotionTask] = []
    for page in body.get("results", []) if isinstance(body, dict) else []:
        if not isinstance(page, dict) or not page.get("id"):
            continue
        title = _title(page)
        if not title:
            continue
        tasks.append(NotionTask(id=str(page["id"]), title=title))
    return tasks
