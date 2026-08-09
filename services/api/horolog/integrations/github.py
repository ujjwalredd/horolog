"""GitHub — pull assigned issues as schedulable work.

Returns `GithubIssue`, not `Intent`, for the same reason as `linear.py`: the
domain model owns chunking and grid-alignment rules, and the API converts
through the ordinary `IntentIn.to_domain` path so an integration cannot drift
from what every other intent obeys.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

DEFAULT_MINUTES = 60
"""GitHub issues carry no duration estimate at all, so every issue gets the
same starting size. Wrong-but-visible on the calendar beats not scheduled."""


class GithubIssue(BaseModel):
    """One assigned issue, reduced to what the scheduler needs."""

    id: str
    number: int
    title: str = Field(min_length=1)
    minutes: int = DEFAULT_MINUTES


class GithubError(RuntimeError):
    """GitHub could not be read. Message is fit to show a user."""


async def fetch_github_issues(token: str, timeout: float = 30.0) -> list[GithubIssue]:
    """Every open issue assigned to the token's owner, across every repo.

    Pull requests share this endpoint in GitHub's API (a PR *is* an issue with
    extra fields) and are filtered out — reviewing a PR is not a chunk of solo
    work the solver should be carving focus time for.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://api.github.com/issues",
                params={"filter": "assigned", "state": "open", "per_page": 100},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise GithubError(f"could not reach GitHub: {exc}") from exc
    except ValueError as exc:
        raise GithubError("GitHub returned something that was not JSON") from exc

    issues: list[GithubIssue] = []
    for node in body if isinstance(body, list) else []:
        if "pull_request" in node:
            continue
        title = (node.get("title") or "").strip()
        if not node.get("id") or not title:
            continue
        issues.append(GithubIssue(id=str(node["id"]), number=node.get("number", 0), title=title))
    return issues
