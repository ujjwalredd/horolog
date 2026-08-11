# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
There is no automated schema-migration tooling (see
[docs/BACKUP.md](docs/BACKUP.md)) — an entry here will call out explicitly
when a change touches the database schema, so back up first if it does.

## [0.2.0]

**Action required to use write-back:** reconnect Google and/or Outlook in
Calendars & Sync. Their OAuth scopes changed (`_SCOPES` in
`services/api/horolog/oauth.py`) to add calendar write access — a token
issued under the old, read-only scope keeps working for read sync but is
rejected by the new push endpoint until reconnected. Nothing else requires
action; read sync, trackers and everything else are unaffected.

### Added
- **Two-way calendar write-back.** Every scheduled block can now be pushed
  onto a dedicated "Horolog" calendar on a connected Google or Outlook
  account, as a real event — never the primary calendar, so it can never be
  read back as busy time the solver then schedules around. Off by default
  (`HOROLOG_CALENDAR_WRITEBACK_ENABLED`); push happens on the existing
  background sync tick once enabled, or on demand via the new push button in
  Calendars & Sync / `POST /api/calendar/push`. The push is a diff against
  the previous push, not a wipe-and-recreate — the same two-pass placement
  property that limits a re-solve to moving only the blocks actually hit
  limits a push to one API call per block actually hit.
  New table: `synced_blocks` (created automatically by `init_db()`).
- **Task completion.** `POST`/`DELETE /api/intents/{id}/complete` marks a
  one-shot task done or undoes it — its remaining demand is skipped on the
  next solve, freeing whatever capacity it still held, while the row itself
  is kept (not deleted) so the inbox and analytics can still show it was
  finished. Scoped to one-shot tasks; a recurring habit needs per-occurrence
  completion, not built yet. New `Intent.completed_at` field — existing rows
  load fine with no migration, since the schema of record is the Pydantic
  model, not the column list.
- **Editing an intent.** `PUT /api/intents/{id}` replaces an intent in place
  while keeping its id, so the previous plan's placement stability carries
  over for every chunk still legal under the new shape — unlike delete-and-
  recreate, which reshuffled the whole week for an unrelated field change.

### Fixed
- Google and Outlook calendar sync (`fetch`) silently truncated past 250
  events with no pagination — the same bug class fixed for the Notion/
  ClickUp/Jira integrations in 0.1.0's QA pass, now closed for the calendar
  read side too.

## [0.1.0]

The first documented state of the project.

### Added
- Placement engine: a two-pass greedy scheduler (`services/api/horolog/solver/`) —
  priority preemption, bounded churn across re-solves, honest unmet-demand
  reporting. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for why this
  replaced an earlier OR-Tools CP-SAT implementation.
- One `Intent` model, five kinds: Task, Habit, Focus, Buffer, Meeting.
- Calendar sync: Google and Outlook via OAuth (with a background re-sync
  loop), plus ICS feeds and CalDAV servers.
- Tracker integrations: Linear, Todoist, GitHub Issues.
- Natural-language capture (`⌘K`) via any OpenAI-compatible or Anthropic
  model, schema-constrained at decode time.
- Smart Meetings: attendee free/busy intersection that never blocks the
  user's own solo work.
- Decompression buffers, booking links (`/book/<name>`), productivity
  analytics.
- Frontend: Planner (month/week/day/list), Task inbox, Habits & Focus Time,
  Meetings, Analytics, Calendars & Sync, and a live Time view — Next.js 15,
  Tailwind v4.
- `python -m horolog.seed_demo` for a believable sample week on a fresh
  install; `python -m horolog.bench` for solve-time/quality benchmarking.
