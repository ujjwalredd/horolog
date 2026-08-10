# Contributing to Horolog

Thank you for your interest in contributing to Horolog! Horolog is an open-source, self-hosted AI calendar engine that defends user focus time. We welcome contributions of all kinds, including bug fixes, feature proposals, documentation improvements, and performance enhancements.

---

## 📜 Principles & Core Constraints

Before making changes, please keep our core invariants in mind:

1. **The placement engine (`services/api/horolog/solver/`) is the core product.**
   - Everything else (HTTP endpoints, database, LLM capture, frontend UI) is I/O built around it.
   - The engine operates purely on **15-minute integer slots** relative to a horizon origin. It must remain free of I/O, datetimes, and timezone logic.
2. **Stability & Bounded Churn (Minimal Perturbation Placement)**:
   - When a new meeting or event lands in a schedule, Horolog **only moves blocks that collided**. Re-planning must never cause a cascading shift of unaffected tasks across the week.
   - The property tests in [`services/api/tests/test_solver.py`](services/api/tests/test_solver.py) pin these invariants. All property tests must pass on every PR.
3. **Honest Shortfall**:
   - Time that does not fit is reported in `unmet`, never dropped silently.
4. **Local-First & Privacy Preserving**:
   - Zero telemetry. Nothing leaves the host machine unless explicitly configured by the user (e.g. cloud LLM providers).

---

## 🛠️ Development Setup

### Requirements
- **Python**: 3.12+
- **Node.js**: 20+
- **`uv`**: Recommended Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/ujjwalredd/horolog.git
cd horolog

# Initialize Python virtual environment & dependencies
cd services/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cd -

# Initialize Web frontend dependencies
cd apps/web && npm install && cd -

# Copy example environment configuration
cp .env.example .env
```

### Running Locally

To launch both the API backend and Next.js frontend together with dynamic free-port selection:

```bash
npm run dev
```

```
  Horolog
  api  http://localhost:8001
  web  http://localhost:3000
```

---

## 🧪 Testing & Verification

Run the full automated check suite before submitting a pull request:

```bash
# Run full suite (Ruff linting, Ruff formatting check, Mypy strict, Pytest, TypeScript & Next.js build)
npm run check

# Run Python API tests only
npm test

# Run solver benchmark
npm run bench
```

### Benchmarking Rule for Placement Engine Edits
If you touch anything in `services/api/horolog/solver/`, you **must** run `npm run bench` before and after your changes and include the benchmark output table in your Pull Request description.

Example benchmark output:
```
horizon 2016 slots (21 days), 9:00-18:00 workday
demand held at 85% of open capacity | 7 runs each

 intents   reqs   load  blocks  cold p50  cold p95  warm p50  warm p95  unmet  churn
      30     70   84%     107      3.8ms     4.6ms     3.0ms     5.3ms      5      0
     100    232   86%     224     13.6ms    14.8ms     8.9ms    16.9ms      8      0
     300    700  185%     335     59.6ms    92.2ms    54.2ms    64.2ms    365      0
```

---

## 🔌 Adding a Provider or Integration

Both patterns below are already minimal by design — the shared helpers do the
heavy lifting, so a new provider is genuinely a small diff. Read the
reference file named in each case before writing anything; copy its shape
rather than inventing a new one.

### A calendar provider (Google/Outlook/ICS/CalDAV today)

1. Implement the `CalendarProvider` protocol in a new file under
   `services/api/horolog/integrations/`:
   ```python
   class CalendarProvider(Protocol):
       async def fetch(self, origin: datetime, horizon_days: int) -> list[BusyInterval]: ...
   ```
   (`services/api/horolog/providers.py`). Reuse `to_interval()` and
   `as_datetime()` from that same file to convert what the upstream API
   returns into `BusyInterval`s, and raise `SyncError` (message fit to show a
   user) on failure. **Reference implementation:**
   `services/api/horolog/integrations/google_calendar.py` — its own docstring
   states the contract explicitly.
2. Add one `POST /api/sync/<provider>` endpoint in `api.py` that builds your
   provider and calls the shared `_mirror()` helper — copy `sync_google`/
   `sync_outlook` (`api.py`, search `@app.post("/api/sync/google")`), about
   six lines.
3. If it's OAuth-based: add entries to `oauth.py`'s `_AUTH_URLS`,
   `_TOKEN_URLS`, `_SCOPES`, `CALENDAR_PROVIDERS`, and `REFRESHABLE` (if it
   supports refresh tokens), plus two new `Settings` fields
   (`<provider>_client_id` / `_client_secret`) in `settings.py`. Document the
   new env vars in `.env.example`, following the existing entries' format
   (registration URL + redirect URI).
4. Frontend: add the provider to the `Provider` type in
   `apps/web/app/lib/api.ts` and a button entry in
   `apps/web/app/connect/page.tsx`'s `CALENDAR_PROVIDERS` array.

### A tracker integration (Linear/Todoist/GitHub/Notion/ClickUp/Jira today)

1. A Pydantic model for one task + a `fetch_*` function + one `*Error`
   exception subclassing `RuntimeError`, in a new file under
   `services/api/horolog/integrations/`. **Reference implementation:**
   `services/api/horolog/integrations/todoist.py` — 77 lines, nothing more
   than that shape.
2. One endpoint in `api.py` using the shared `_sync_tasks()` helper (search
   `async def _sync_tasks`), which already reduces storage to a
   `(id, title, priority, minutes)` tuple regardless of source.
3. If OAuth-based, same `oauth.py`/`settings.py`/`.env.example` steps as
   above, added to `TRACKER_PROVIDERS` instead of `CALENDAR_PROVIDERS`. A
   personal-API-key tracker (no OAuth app needed) can skip straight to the
   endpoint — see how Todoist's pasted-key path works in `sync_todoist`, or
   `notion.py`/`clickup.py`/`jira.py` for a *key-only* tracker with no OAuth
   path at all (worth checking first: does the provider's own API even fit
   OAuth cleanly, or — like Jira's cloud-id indirection — is a pasted
   credential actually the better-fitting choice? See `jira.py`'s docstring
   for a real example of that trade-off). A credential needing more than one
   part (e.g. Jira's `site:email:api_token`) is packed into the single pasted
   string and split inside `fetch_*` — no frontend change needed.

---

## 📥 Submitting a Pull Request

1. **Fork the repository** and create a feature branch (`git checkout -b feature/my-feature`).
2. Keep commits concise and descriptive.
3. Ensure `npm run check` passes cleanly.
4. Open a Pull Request against the `main` branch. Describe the motivation for the change and include any relevant benchmark numbers or screenshots.

---

## 📄 License

By contributing to Horolog, you agree that your contributions will be licensed under the project's [AGPL-3.0 License](LICENSE).
