"""ClickUp — pull tasks assigned to the token owner as schedulable work."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from horolog.domain.intent import Priority
from horolog.domain.time import SLOT_MINUTES

DEFAULT_MINUTES = 45
"""What an un-estimated task is worth — same reasoning as todoist.py's."""

MAX_PAGES = 10
"""ClickUp returns up to 100 tasks per page — a hard cap on pages, not on
tasks found, so a pathological workspace cannot turn one sync into an
unbounded number of requests."""

# ClickUp's 1 (urgent) .. 4 (low) already matches Horolog's P1..P4 numbering.
_PRIORITY_MAP = {1: Priority.P1, 2: Priority.P2, 3: Priority.P3, 4: Priority.P4}


class ClickUpTask(BaseModel):
    """One task, reduced to what the scheduler needs."""

    id: str
    name: str = Field(min_length=1)
    priority: Priority = Priority.P3
    minutes: int = DEFAULT_MINUTES


class ClickUpError(RuntimeError):
    """ClickUp could not be read. Message is fit to show a user."""


def _minutes_for(task: dict[str, object]) -> int:
    """ClickUp's own time estimate, in milliseconds, rounded up to the grid."""
    estimate = task.get("time_estimate")
    if isinstance(estimate, int | float) and estimate > 0:
        minutes = int(estimate) // 60_000
        return max(SLOT_MINUTES, -(-minutes // SLOT_MINUTES) * SLOT_MINUTES)
    return DEFAULT_MINUTES


async def fetch_clickup_tasks(credential: str, timeout: float = 30.0) -> list[ClickUpTask]:
    """Every open task assigned to the token owner, from a pasted
    `team_id:api_token`.

    ClickUp calls this a "workspace" in its own UI but still "team_id" in the
    API and in the URL your workspace's settings page links to. There is no
    "assignee=me" the API accepts directly, so this makes two calls: who the
    token belongs to, then that user's open tasks — without it, every user's
    tasks in the workspace would come back, not just the token owner's.
    """
    team_id, _, token = credential.partition(":")
    team_id, token = team_id.strip(), token.strip()
    if not team_id or not token:
        raise ClickUpError("expected team_id:api_token")

    headers = {"Authorization": token}
    tasks: list[ClickUpTask] = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            me = await client.get("https://api.clickup.com/api/v2/user", headers=headers)
            me.raise_for_status()
            user_id = me.json()["user"]["id"]

            for page in range(MAX_PAGES):
                response = await client.get(
                    f"https://api.clickup.com/api/v2/team/{team_id}/task",
                    headers=headers,
                    params={
                        "assignees[]": str(user_id),
                        "include_closed": "false",
                        "page": str(page),
                    },
                )
                response.raise_for_status()
                body = response.json()
                nodes = body.get("tasks", []) if isinstance(body, dict) else []
                if not nodes:
                    break
                for node in nodes:
                    if not isinstance(node, dict) or not node.get("id"):
                        continue
                    name = (node.get("name") or "").strip()
                    if not name:
                        continue
                    priority_node = node.get("priority")
                    priority_id = 3
                    if isinstance(priority_node, dict) and priority_node.get("id"):
                        try:
                            priority_id = int(priority_node["id"])
                        except (TypeError, ValueError):
                            priority_id = 3
                    tasks.append(
                        ClickUpTask(
                            id=str(node["id"]),
                            name=name,
                            priority=_PRIORITY_MAP.get(priority_id, Priority.P3),
                            minutes=_minutes_for(node),
                        )
                    )
                # ClickUp doesn't report a total — a short page is the only
                # signal that there's nothing left to fetch.
                if len(nodes) < 100:
                    break
    except httpx.HTTPError as exc:
        raise ClickUpError(f"could not reach ClickUp: {exc}") from exc
    except (ValueError, KeyError) as exc:
        raise ClickUpError("ClickUp returned something unexpected") from exc

    return tasks
