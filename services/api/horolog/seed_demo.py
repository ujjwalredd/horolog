"""Optional demo data for a fresh install.

    python -m horolog.seed_demo

Posts a believable week — one habit, one focus-time goal, two tasks with due
dates, one smart meeting — through the real, validated `/api/intents` path
(`IntentIn.to_domain()` in `api.py`), the same one the UI and NL capture use.

Never runs on its own: nothing in `lifespan()`/`init_db()` calls this, and it
never writes to the database directly. Requires a running server
(`npm run dev`, or `npm run dev:api`).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Any

import httpx

DEMO_INTENTS: list[dict[str, Any]] = [
    {
        "title": "Gym",
        "kind": "habit",
        "priority": 3,
        "minutes_per_period": 180,
        "period_days": 7,
        "min_chunk_minutes": 60,
        "max_chunk_minutes": 60,
        "max_per_day": 1,
        "window_start_min": 10 * 60,
        "window_end_min": 16 * 60,
    },
    {
        "title": "Deep work",
        "kind": "focus",
        "priority": 2,
        "energy": "high",
        "minutes_per_period": 600,
        "period_days": 7,
        "min_chunk_minutes": 90,
        "max_chunk_minutes": 120,
    },
    {
        "title": "Finish Q3 report",
        "kind": "task",
        "priority": 1,
        "minutes_per_period": 180,
        "min_chunk_minutes": 60,
        "max_chunk_minutes": 120,
        "due": (datetime.now() + timedelta(days=3)).isoformat(),
    },
    {
        "title": "Prep client presentation",
        "kind": "task",
        "priority": 2,
        "minutes_per_period": 90,
        "min_chunk_minutes": 45,
        "max_chunk_minutes": 90,
        "due": (datetime.now() + timedelta(days=5)).isoformat(),
    },
    {
        "title": "Weekly sync",
        "kind": "meeting",
        "priority": 2,
        "minutes_per_period": 60,
        "min_chunk_minutes": 60,
        "max_chunk_minutes": 60,
        "attendee_busy": [
            {
                "start": (datetime.now().replace(hour=9, minute=0) + timedelta(days=d)).isoformat(),
                "end": (datetime.now().replace(hour=15, minute=0) + timedelta(days=d)).isoformat(),
                "attendee": "colleague@example.com",
            }
            for d in range(5)
        ],
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000", help="running API base URL")
    parser.add_argument("--force", action="store_true", help="seed even if intents already exist")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=10.0) as client:
        try:
            client.get("/api/health").raise_for_status()
        except httpx.HTTPError as exc:
            print(f"cannot reach {args.url} - is `npm run dev` running? ({exc})", file=sys.stderr)
            raise SystemExit(1) from exc

        existing = client.get("/api/intents").json()
        if existing and not args.force:
            print(
                f"{len(existing)} intent(s) already exist at {args.url} - refusing to seed "
                "demo data over real data. Pass --force to add anyway.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        for intent in DEMO_INTENTS:
            response = client.post("/api/intents", json=intent)
            response.raise_for_status()
            print(f"  seeded: {intent['title']}")

    print(f"\nDone. Open {args.url.replace('8000', '3000')} to see the week.")


if __name__ == "__main__":
    main()
