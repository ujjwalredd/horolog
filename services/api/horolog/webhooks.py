from __future__ import annotations

import httpx

from horolog.domain.intent import IntentKind


async def send_status_webhook(
    webhook_url: str,
    event_title: str,
    kind: IntentKind,
    status_text: str,
) -> bool:
    """Post an active status update to a Slack or Discord webhook."""
    emoji = "🤫" if kind == IntentKind.FOCUS else "📅" if kind == IntentKind.MEETING else "⚡"
    payload = {
        "text": f"{emoji} *Horolog Focus Status*: {status_text} (`{event_title}`)",
        "content": f"{emoji} **Horolog Focus Status**: {status_text} (`{event_title}`)",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(webhook_url, json=payload)
            return resp.status_code < 400
        except Exception:
            return False
