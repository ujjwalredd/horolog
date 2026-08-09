from __future__ import annotations

import httpx

from horolog.domain.intent import Intent, IntentKind, Priority


async def fetch_linear_tasks(api_key: str) -> list[Intent]:
    """Fetch 'In Progress' tasks from Linear and convert them to Horolog Intents."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.linear.app/graphql",
            headers={"Authorization": api_key},
            json={
                "query": (
                    '{ issues(filter: { state: { name: { eq: "In Progress" } } }) '
                    '{ nodes { id title estimate } } }'
                )
            }
        )
        response.raise_for_status()
        data = response.json()
        intents = []
        for issue in data.get("data", {}).get("issues", {}).get("nodes", []):
            # Map linear points to duration (1 point = 60 mins)
            # Default to 60 mins if estimate is missing
            estimate_mins = (issue.get("estimate") or 1) * 60
            
            intents.append(Intent(
                id=f"linear_{issue['id']}",
                title=f"Linear: {issue['title']}",
                kind=IntentKind.TASK,
                priority=Priority.P2,
                duration_mins=estimate_mins,
                splittable=True
            ))
        return intents
