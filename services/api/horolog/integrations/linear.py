"""Linear — pull in-progress issues as schedulable work.

Deliberately returns `LinearIssue`, not `Intent`. The domain model enforces
chunking, grid alignment and window rules that an integration has no business
re-deriving; the API converts these through the same `IntentIn.to_domain` path
every other intent takes.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from horolog.domain.time import SLOT_MINUTES

QUERY = """
query InProgress {
  issues(filter: { state: { type: { eq: "started" } } }, first: 100) {
    nodes { id identifier title estimate }
  }
}
"""

MINUTES_PER_POINT = 60
"""Linear estimates are unitless points. One point = one hour is the convention
most teams land on, and the only assumption here — override by editing the
issue's duration once it has been imported."""

DEFAULT_MINUTES = 60
"""What an unestimated issue is worth. Better than skipping it: an unestimated
task is still work, and a wrong hour is visible and fixable where an absent task
is neither."""


class LinearIssue(BaseModel):
    """One issue, reduced to what the scheduler needs."""

    id: str
    identifier: str = ""
    """The human key (`ENG-214`). Empty when Linear omits it."""

    title: str = Field(min_length=1)
    minutes: int = Field(gt=0)


class LinearError(RuntimeError):
    """The issue tracker could not be read. Message is fit to show a user."""


def _minutes_for(estimate: float | None) -> int:
    """Points to a whole number of scheduling slots' worth of minutes.

    Rounded *up* to the grid for the same reason `minutes_to_slots` rounds up:
    booking 55 minutes for an hour of work reports it done while it is not.
    """
    raw = round((estimate or 0) * MINUTES_PER_POINT) or DEFAULT_MINUTES
    return -(-raw // SLOT_MINUTES) * SLOT_MINUTES


async def fetch_linear_issues(api_key: str, timeout: float = 30.0) -> list[LinearIssue]:
    """Every started issue assigned within the caller's Linear workspace.

    `state.type == "started"` rather than a literal name: "In Progress" is only
    the default label and any workspace can rename it, whereas the type is part
    of Linear's schema and cannot be.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.linear.app/graphql",
                headers={"Authorization": api_key},
                json={"query": QUERY},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise LinearError(f"could not reach Linear: {exc}") from exc
    except ValueError as exc:
        raise LinearError("Linear returned something that was not JSON") from exc

    # GraphQL reports failures in a 200 body, so a raise_for_status pass says
    # nothing about whether the query actually worked.
    if errors := body.get("errors"):
        message = "; ".join(str(e.get("message", e)) for e in errors)
        raise LinearError(f"Linear rejected the query: {message}")

    nodes = (body.get("data") or {}).get("issues", {}).get("nodes") or []
    issues: list[LinearIssue] = []
    for node in nodes:
        title = (node.get("title") or "").strip()
        if not node.get("id") or not title:
            continue
        issues.append(
            LinearIssue(
                id=str(node["id"]),
                identifier=str(node.get("identifier") or ""),
                title=title,
                minutes=_minutes_for(node.get("estimate")),
            )
        )
    return issues
