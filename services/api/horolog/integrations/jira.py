"""Jira — pull issues assigned to the token owner as schedulable work."""

from __future__ import annotations

import base64

import httpx
from pydantic import BaseModel, Field

from horolog.domain.intent import Priority
from horolog.domain.time import SLOT_MINUTES

DEFAULT_MINUTES = 45
"""What an un-estimated issue is worth — same reasoning as todoist.py's."""

# Jira Cloud's default priority scheme, highest to lowest. A site that has
# renamed or added priorities falls through to the P3 default below rather
# than raising — an unrecognised name is not a reason to fail the sync.
_PRIORITY_MAP = {
    "Highest": Priority.P1,
    "High": Priority.P2,
    "Medium": Priority.P3,
    "Low": Priority.P4,
    "Lowest": Priority.P4,
}


class JiraIssue(BaseModel):
    """One issue, reduced to what the scheduler needs."""

    id: str
    key: str = ""
    summary: str = Field(min_length=1)
    priority: Priority = Priority.P3
    minutes: int = DEFAULT_MINUTES


class JiraError(RuntimeError):
    """Jira could not be read. Message is fit to show a user."""


def _minutes_for(fields: dict[str, object]) -> int:
    """Jira's remaining time estimate, in seconds, rounded up to the grid."""
    estimate = fields.get("timeestimate")
    if isinstance(estimate, int | float) and estimate > 0:
        minutes = int(estimate) // 60
        return max(SLOT_MINUTES, -(-minutes // SLOT_MINUTES) * SLOT_MINUTES)
    return DEFAULT_MINUTES


async def fetch_jira_issues(credential: str, timeout: float = 30.0) -> list[JiraIssue]:
    """Every unresolved issue assigned to the token owner, from a pasted
    `site:email:api_token`.

    `site` is the subdomain in `https://{site}.atlassian.net`. The API token
    comes from id.atlassian.com/manage-profile/security/api-tokens — Jira
    Cloud's REST API takes Basic auth (email + token), not a bearer token, so
    this is a three-part credential rather than the single string every other
    tracker here takes.
    """
    parts = credential.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise JiraError("expected site:email:api_token")
    site, email, token = parts

    basic = base64.b64encode(f"{email}:{token}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"https://{site}.atlassian.net/rest/api/3/search",
                headers={"Authorization": f"Basic {basic}", "Accept": "application/json"},
                params={
                    "jql": "assignee = currentUser() AND resolution = Unresolved",
                    "fields": "summary,priority,timeestimate",
                },
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise JiraError(f"could not reach Jira: {exc}") from exc
    except ValueError as exc:
        raise JiraError("Jira returned something that was not JSON") from exc

    issues: list[JiraIssue] = []
    for node in body.get("issues", []) if isinstance(body, dict) else []:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        raw_fields = node.get("fields")
        fields: dict[str, object] = raw_fields if isinstance(raw_fields, dict) else {}
        summary = str(fields.get("summary") or "").strip()
        if not summary:
            continue
        priority_field = fields.get("priority")
        priority_name = priority_field.get("name") if isinstance(priority_field, dict) else None
        priority = _PRIORITY_MAP.get(priority_name, Priority.P3) if priority_name else Priority.P3
        issues.append(
            JiraIssue(
                id=str(node["id"]),
                key=str(node.get("key", "")),
                summary=summary,
                priority=priority,
                minutes=_minutes_for(fields),
            )
        )
    return issues
