# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
There is no automated schema-migration tooling (see
[docs/BACKUP.md](docs/BACKUP.md)) — an entry here will call out explicitly
when a change touches the database schema, so back up first if it does.

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
