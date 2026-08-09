"""Todoist — pull uncompleted tasks as schedulable work.

Returns `TodoistTask`, not `Intent` — see `linear.py` for why: the domain
model owns chunking and grid-alignment, and the API converts through the
ordinary `IntentIn.to_domain` path.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from horolog.domain.intent import Priority
from horolog.domain.time import SLOT_MINUTES

DEFAULT_MINUTES = 45
"""What an un-timed task is worth. Todoist tasks rarely carry a duration —
most users never fill it in — so most imported tasks land on this default."""

# Todoist's 1 (lowest) .. 4 (highest) maps onto Horolog's P1 (highest) .. P4.
_PRIORITY_MAP = {4: Priority.P1, 3: Priority.P2, 2: Priority.P3, 1: Priority.P4}


class TodoistTask(BaseModel):
    """One uncompleted task, reduced to what the scheduler needs."""

    id: str
    content: str = Field(min_length=1)
    priority: Priority = Priority.P3
    minutes: int = DEFAULT_MINUTES


class TodoistError(RuntimeError):
    """Todoist could not be read. Message is fit to show a user."""


def _minutes_for(task: dict[str, object]) -> int:
    """Round a stated duration up to the scheduling grid; fall back otherwise."""
    duration = task.get("duration")
    if isinstance(duration, dict) and duration.get("unit") == "minute":
        amount = duration.get("amount")
        if isinstance(amount, int | float) and amount > 0:
            return -(-int(amount) // SLOT_MINUTES) * SLOT_MINUTES
    return DEFAULT_MINUTES


async def fetch_todoist_tasks(token: str, timeout: float = 30.0) -> list[TodoistTask]:
    """Every uncompleted task in the token owner's Todoist account."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://api.todoist.com/rest/v2/tasks",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise TodoistError(f"could not reach Todoist: {exc}") from exc
    except ValueError as exc:
        raise TodoistError("Todoist returned something that was not JSON") from exc

    tasks: list[TodoistTask] = []
    for node in body if isinstance(body, list) else []:
        if node.get("is_completed") or not node.get("id"):
            continue
        content = (node.get("content") or "").strip()
        if not content:
            continue
        tasks.append(
            TodoistTask(
                id=str(node["id"]),
                content=content,
                priority=_PRIORITY_MAP.get(node.get("priority", 1), Priority.P3),
                minutes=_minutes_for(node),
            )
        )
    return tasks
