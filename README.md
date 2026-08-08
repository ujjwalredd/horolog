# Horolog

[![AGPL-3.0 License](https://img.shields.io/badge/License-AGPL_3.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](services/api/pyproject.toml)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-000000.svg?logo=next.js&logoColor=white)](apps/web/package.json)
[![CI Status](https://img.shields.io/github/actions/workflow/status/ujjwalredd/horolog/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)

**An open-source, self-hosted AI calendar that defends your time.**

Horolog places focus time, habits and tasks around the meetings you actually
have - then keeps them there. It runs entirely on your own machine, against your
own calendar, with whichever language model you already trust.

It is a working alternative to [Reclaim.ai](https://reclaim.ai) (acquired by
Dropbox in 2024). At the time of writing no open-source equivalent existed:
Cal.com covers booking links, but the auto-scheduling half - focus time, habits,
priority preemption, automatic rescheduling - had not been built in the open.

```bash
git clone https://github.com/ujjwalredd/horolog.git && cd horolog
cp .env.example .env
docker compose -f infra/docker-compose.yml up
# → http://localhost:3000
```

No account. No telemetry. Nothing leaves the machine.

---

## Why this exists

Most "AI calendar" tools re-plan your entire week whenever anything changes, so
you stop trusting what you see. Horolog optimises for the opposite:

| | |
|---|---|
| **Re-plan latency** | **0.6–97 ms** (Reclaim documents ~15 s) |
| **Blocks moved when a meeting lands** | **only the ones it hit** - verified by test, not asserted |
| **Re-plan with nothing changed** | a provable no-op, to the slot |
| **Where your calendar lives** | your machine |
| **Model** | Ollama, vLLM, SGLang, llama.cpp, Anthropic, OpenAI - your choice |

The stability guarantee is the point. Measured on 20 blocks with an eight-hour
meeting dropped into the middle of the week: **4 blocks collided, 4 blocks
moved, 16 untouched.** An earlier single-pass placer moved 16 of 20 - the
regression test that pins this is
[`test_a_busy_week_does_not_cascade`](services/api/tests/test_solver.py).

---

## The five agents

Each is the same scheduling primitive wearing a different hat - one engine, not
five subsystems. See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for why that matters.

| Agent | What it does |
|---|---|
| **Smart Task Scheduler** | Deadline-aware tasks, split across sittings and placed around real meetings. Priority P1–P4 decides who wins a contested slot. |
| **Habit & Routine Manager** | "Gym three times a week between 10 and 4." Recurrence, time-of-day windows, per-day caps, automatic relocation. |
| **Dynamic Calendar Sync** | ICS feeds and CalDAV servers in, an ICS feed of your plan back out. Recurring events expanded; free/transparent events ignored. |
| **Smart Meetings** | Multi-attendee scheduling that intersects everyone's availability - without letting a colleague's calendar block your own solo work. |
| **Productivity Analytics** | Deep-work hours, meeting load, fragmentation, longest free run per day, after-hours load, unmet demand. |

---

## Screens

| | |
|---|---|
| **Planner** | Week grid. Priority by accent weight, kind by glyph, movability by rule style. Live over SSE. |
| **Task inbox** | Every intent and where it actually landed. Anything that did not fit is called out, not hidden. |
| **Habits** | Builds routines in the units people speak - "3× a week, an hour each, between 10 and 4". |
| **Analytics** | Stat tiles plus a per-day load chart. Palette validated for colour-vision deficiency, not eyeballed. |
| **Calendars** | Connect an ICS feed or a CalDAV server; export your plan as a subscribable feed. |

`⌘K` anywhere opens natural-language capture: *"write the design doc, about
three hours, by Friday"*.

---

## Bring your own model

The model only ever fills in a form. It reads your sentence and produces a
schema-checked request; it never picks a time and it cannot write to your
calendar. The scheduler does that, from your real availability. Output is
constrained at decode time, so malformed answers are not caught - they are
impossible.

```bash
# Local, zero cost (default)
HOROLOG_LLM_PROVIDER=openai
HOROLOG_LLM_BASE_URL=http://localhost:11434/v1
HOROLOG_LLM_MODEL=qwen3:8b

# Anthropic
HOROLOG_LLM_PROVIDER=anthropic
HOROLOG_LLM_MODEL=claude-opus-5
HOROLOG_LLM_API_KEY=sk-ant-...

# OpenAI, or anything OpenAI-compatible (vLLM, SGLang, Groq, Together)
HOROLOG_LLM_PROVIDER=openai
HOROLOG_LLM_BASE_URL=https://api.openai.com/v1
HOROLOG_LLM_MODEL=gpt-4.1
HOROLOG_LLM_API_KEY=sk-...
```

Anthropic needs the optional extra: `pip install 'horolog[anthropic]'`
(already included in the Docker image).

---

## Local development

**Requirements:** Python 3.12+, Node 20+. No database server needed - SQLite by
default.

```bash
# once
cd services/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cd -
cd apps/web && npm install && cd -

# every time - starts the API and the web app together
npm run dev
```

```
  api: 8000 is in use, using 8001
  Horolog
  api  http://localhost:8001
  web  http://localhost:3000
```

`npm run dev` picks free ports rather than assuming 8000/3000, wires the web
app's proxy to whichever port the API got, clears any `.next` left behind by a
production build, and shuts both halves down together. Running the two by hand
works too (`npm run dev:api`, `npm run dev:web`) - just don't start two
`next dev` processes against the same checkout, because they share `.next` and
overwrite each other's chunks.

The web app proxies `/api/*` to the API, so the browser sees one origin and
there is no CORS to configure. Override with `HOROLOG_API_URL`.

### Tests and checks

```bash
npm test       # 45 tests, ~1s
npm run bench  # solve-time + quality benchmark
npm run check  # ruff + ruff format + mypy strict + pytest, then tsc + next build
```

The suite is fast on purpose - the scheduling engine has no I/O, so its
properties are checked directly rather than through a server.

### Benchmark

```
$ python -m horolog.bench
horizon 2016 slots (21 days), 9:00-18:00 workday
demand held at 85% of open capacity | 7 runs each

 intents   reqs   load  blocks  cold p50  cold p95  warm p50  warm p95  unmet
      30     70   84%     107      3.8ms     4.6ms     3.0ms     5.3ms      5
     100    232   86%     224     13.6ms    14.8ms     8.9ms    16.9ms      8
     300    700  185%     335     59.6ms    92.2ms    54.2ms    64.2ms    365
```

The 300-intent row is deliberately over-subscribed (185% of capacity) - the
`unmet` column is correct behaviour there, not a failure.

---

## Configuration

Every setting is read from the environment with a `HOROLOG_` prefix and
validated at boot, so a bad value fails the process rather than the first
request that needs it. Full list in [`.env.example`](.env.example).

The one worth knowing: `HOROLOG_TIMEZONE` defaults to the host's own zone. Left
at UTC on a machine that isn't, a 9-to-5 goal silently lands at 5am.

---

## Deployment

```bash
docker compose -f infra/docker-compose.yml up -d
```

Brings up the API, the web app, Postgres, and Ollama with a small model pulled
on first boot. For SQLite instead of Postgres, drop the `db` service and set
`HOROLOG_DATABASE_URL=sqlite+aiosqlite:///./data/horolog.db`.

**Authentication:** this build is single-user and unauthenticated by design - it
runs on your machine against your calendar. For a team instance, put it behind
an SSO proxy (oauth2-proxy, Authelia, Tailscale, Cloudflare Access) rather than
exposing it directly. Horolog trusts the identity your proxy asserts instead of
rolling its own credential store.

---

## Project layout

```
services/api/horolog/
  domain/       Pydantic contracts - the single source of truth
  solver/       expand → greedy placement → score
  providers.py  ICS + CalDAV
  llm.py        multi-provider structured extraction
  capture.py    natural language → validated intent
  analytics.py  derived metrics
  api.py        HTTP surface + SSE
apps/web/app/   Next.js 15, App Router, Tailwind v4
docs/           ARCHITECTURE.md
infra/          docker-compose + Dockerfiles
```

---

## Contributing

We welcome contributions! Please read our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting pull requests.

The engine is the product; everything else is I/O around it. If you change
anything under `solver/`, the property tests in
[`services/api/tests/test_solver.py`](services/api/tests/test_solver.py) are the contract - they encode behaviour
(no overlap, bounded churn, honest shortfall) rather than implementation, so a
better algorithm should keep them all passing.

Run `python -m horolog.bench` before and after any placement change and put the
numbers in the PR.

## Security

Please see our [Security Policy](SECURITY.md) for vulnerability reporting guidelines.

## Licence

[AGPL-3.0-or-later](LICENSE). If you run a modified version as a network service, publish your
changes.

**Not affiliated with Reclaim.ai or Dropbox.** "Reclaim.ai" is referenced only
to describe the category this project reimplements.

