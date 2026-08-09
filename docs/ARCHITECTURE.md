# Architecture

![Horolog System & Interface](hero.png)

## The one idea

Calendar tools usually model time as *fixed blocks you place manually*. Horolog
models it as **a demand with a window and a priority**, and re-solves whenever
reality changes. Everything else follows from that.

Focus time, habits, tasks, buffers and smart meetings are **one primitive under
five names** - an activity with a duration, a temporal domain, an
interruptibility, a periodicity and a priority. This is not a simplification
invented here: SelfPlanner (Refanidis & Alexiadis, *ACM TIST*) published exactly
this model as a constraint-optimisation problem a decade before Reclaim shipped.

One table, one placement path. A sixth feature means a new `kind` and a factory
function - never a new scheduler.

```
Intent (one row)                       reads as
──────────────────────────────────     ─────────────────────────────
kind=task,  once,     splittable   →   a deadline-driven task
kind=habit, weekly,   fixed size   →   "gym 3× a week"
kind=focus, weekly,   ≥90m chunks  →   a focus-hours goal
kind=buffer,per-event,fixed        →   decompression after calls
kind=meeting, + attendee busy      →   a smart meeting
```

## Request flow

```
                 ┌──────────── ICS feed / CalDAV server
                 ▼
  ┌────────────────────────────┐
  │ providers.py               │  expand RRULE, honour TRANSP, clip to horizon
  └──────────────┬─────────────┘
                 ▼
          BusyInterval[]  ── the immovable events (busy_events table)
                 │
  "gym 3x a week"│           ┌──────────────────────────────────┐
        ⌘K ──────┼──────────▶│ llm.py → capture.py              │
                 │           │ grammar-constrained → Pydantic   │
                 │           │ → one repair round → or fail     │
                 │           └───────────────┬──────────────────┘
                 │                           ▼
                 │                      Intent (intents table)
                 ▼                           │
  ┌──────────────────────────────────────────▼───────────────────┐
  │ solver/                                                      │
  │   expand.py   Intent  → Requirement[]  (recurrence, windows) │
  │   greedy.py   Requirement[] + busy + previous → Placement    │
  │   score.py    quality metric (a measurement, not a target)   │
  └──────────────────────────┬───────────────────────────────────┘
                             ▼
                       Plan  (plans table, one JSON row)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        GET /api/plan   SSE broadcast   GET /api/plan.ics
```

## The placement engine

`solver/greedy.py` is the whole product. Every trade-off a constraint solver
would express in an objective function is an ordering rule here:

| Concern | How it is expressed |
|---|---|
| Priority preemption | sort key - P1 claims slots before P4 sees them |
| Stability (MPP) | previous placements are *reserved* before anything is reallocated |
| Deadlines | earlier due dates sort first |
| Time of day | window ranking |
| Fragmentation | largest chunks first |
| Per-day caps | a counter |
| Attendee availability | per-requirement blocked spans |

### Why two passes, and why it is not optional

The engine reserves every still-valid previous placement **before** allocating
anything new.

A single pass that merely *prefers* a chunk's old slot looks equivalent and is
not. Requirements are visited in priority order, so a block displaced by a new
meeting reaches the allocator *before* an untouched lower-priority block does,
takes the slot that block was quietly still holding, and evicts it. That
eviction displaces the next one, and the damage cascades.

Measured, 20 blocks, one eight-hour meeting dropped in:

| | blocks moved |
|---|---|
| single pass | **16 of 20** (4 were actually hit) |
| two passes | **4 of 20** |

Pinned by `test_a_busy_week_does_not_cascade`.

### Why not a constraint solver

The first implementation was OR-Tools CP-SAT - optional interval variables,
`NoOverlap`, a weighted objective with a minimal-perturbation term. It was
removed after measurement:

| Instance | Greedy | CP-SAT gain | Time |
|---|---|---|---|
| 30 intents, 84% load | 1.2 ms | **+0.58%** | 2 s |
| 100 intents, 86% load | 3.8 ms | **+0.34%** | 2 s |
| 300 intents, 185% load | 23.7 ms | **+0.00%** | 2 s |
| 40 adversarial (fragmented windows, deadlines, caps) | 0.7 ms | **+0.36%** | 15 s |
| 120 adversarial | 4.4 ms | **−7.97%** (worse) | 15 s |

Half a percent of schedule quality did not justify a 90 MB dependency, a 2-second
budget, presolve tuning, and an OR-Tools crash workaround. `score.py` keeps that
comparison reproducible if anyone wants to re-litigate it - the metric is still
there, nothing optimises it.

## Time representation

The engine works entirely in **integer slots of 15 minutes** from a horizon
origin (midnight today, in the configured zone). No datetimes reach `solver/`.

- Durations round **up** to whole slots. Rounding down would schedule 15 minutes
  for a 20-minute task and then report it finished.
- Datetimes are normalised at the HTTP boundary: naive input is read in the
  configured zone. ICS files and browser `toISOString()` both emit floating
  times, and without that every one of them would 500 in `to_slot`.
- `HOROLOG_TIMEZONE` defaults to the host's zone, read from `$TZ` or
  `/etc/localtime`.

## Database schema

Three tables. Deliberately few - a plan is *derived*, and deriving it costs
single-digit milliseconds, so it is recomputed rather than stored as rows.

### `intents`

| column | type | notes |
|---|---|---|
| `id` | `varchar(64)` PK | 12-char hex |
| `payload` | `JSON` | the full validated `Intent` |
| `created_at` | `timestamptz` | |

The Pydantic model is the schema of record. Shredding it into columns would put
a second copy of the schema in DDL, to be kept in sync by hand.

### `busy_events`

| column | type | notes |
|---|---|---|
| `id` | `varchar(128)` PK | `{source}:{uuid}` |
| `source` | `varchar(32)` | `manual` \| `ics` \| `caldav` - sync replaces per source |
| `label` | `varchar(256)` | |
| `start_slot` | `integer` indexed | |
| `end_slot` | `integer` | |

Slots, not timestamps: this table is read on every re-plan and the engine wants
integers. Overlapping rows are fine - they are merged at solve time, because
real calendars are double-booked constantly.

### `plans`

| column | type | notes |
|---|---|---|
| `id` | `integer` PK | always `1` in single-user mode |
| `payload` | `text` | the previous `Plan` as JSON |
| `saved_at` | `timestamptz` | |

Only the *previous* plan is stored, and only because the placer needs it to stay
stable. It is state for the algorithm, not a record of history.

**Multi-tenancy** is a `user_id` foreign key on all three plus a filter in
`load_intents` / `load_previous_plan`. Nothing else in the schema changes.

## The LLM boundary

The model is confined to one job: turning a sentence into a candidate `Intent`.

1. **Grammar-constrained decoding.** The schema is enforced at the sampling
   stage, so structurally invalid JSON is unrepresentable rather than
   discouraged.
2. **Semantic validation.** Pydantic checks what a grammar cannot - that the
   chunk fits inside the window, that the total exceeds one chunk. One repair
   round carries the error back; a second failure surfaces to a form.
3. **No write path.** The model cannot place time. Only the scheduler can, and
   only against real availability. A hallucinated intent produces a
   wrong-looking task the user can delete - never a phantom calendar event.

Layer 3 is the one that holds under a bad model. Prompt discipline alone would not.

Two providers, because the wire formats genuinely differ: OpenAI-compatible
`response_format`, and Anthropic's `output_config.format` via the official SDK.

## Frontend

Next.js 15 App Router, Tailwind v4, no component library. Light theme only -
a half-tuned second theme reads worse than one exact one.

Design tokens live in `app/globals.css`. Two decisions carry most of the look:

- **Warm-tinted, layered, low-alpha shadows.** Pure-black shadows are most of
  what makes an interface look cheap.
- **`font-variant-numeric: tabular-nums` on every clock time.** Without it,
  digits change width as the plan updates and the grid twitches.

The calendar has to encode 5 kinds × 4 priorities × 3 states in one accent hue.
Only priority uses colour (accent at four weights); kind uses a glyph, movability
uses the left rule style, and other people's meetings use a sunk fill with no
accent at all. That also satisfies "never rely on colour alone".

Chart colours are the exception and are **validated, not chosen** - see the
comment block in `app/analytics/page.tsx` for the recorded CVD separation figures.

## Known ceilings

Marked in the code with `ponytail:` comments.

- **SSE fan-out is in-process.** Multiple API workers each hold their own
  subscriber set, so a change on worker A never reaches a client on worker B.
  Postgres `LISTEN/NOTIFY` when you run more than one process.
- **`SCHEDULING_RANGE_DAYS = 14`.** A requirement is only placed within 14 days
  of its own start, which bounds the search regardless of horizon. Reclaim meters
  the same thing as a plan feature.
- **`MAX_CHUNKS_PER_REQUIREMENT = 16`.** Stops a pathological intent (8 h at
  15-minute chunks) blowing up placement.
- **Single-user.** See the multi-tenancy note above.
