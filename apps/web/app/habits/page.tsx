"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Glyph } from "@/app/components/Glyph";
import { Shell } from "@/app/components/Shell";
import {
  PRIORITY_NAME,
  PRIORITY_TINT,
  api,
  createIntent,
  formatDuration,
  type Intent,
  type Plan,
  type Priority,
} from "@/app/lib/api";

const PRESETS = [
  { title: "Gym", times: 3, minutes: 60, from: 600, to: 960, priority: 4 },
  { title: "Deep work", times: 5, minutes: 120, from: 540, to: 720, priority: 2, kind: "focus" },
  { title: "Lunch", times: 5, minutes: 45, from: 720, to: 840, priority: 3 },
  { title: "Inbox & admin", times: 5, minutes: 30, from: 960, to: 1080, priority: 4 },
] as const;

function clock(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function toMinutes(value: string): number {
  const [h = "0", m = "0"] = value.split(":");
  return Number(h) * 60 + Number(m);
}

/** Habit builder.
 *
 *  The form is shaped the way people describe a routine — "three times a week,
 *  an hour each, between 10 and 4" — rather than the way the engine stores it
 *  (total minutes per period, chunk bounds, per-day cap). The conversion is
 *  four lines; making the user do it in their head is the actual cost.
 */
export default function Habits() {
  const [intents, setIntents] = useState<Intent[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState("");
  const [times, setTimes] = useState(3);
  const [minutes, setMinutes] = useState(60);
  const [from, setFrom] = useState(600);
  const [to, setTo] = useState(960);
  const [priority, setPriority] = useState<Priority>(4);

  const load = useCallback(async () => {
    try {
      const [i, p] = await Promise.all([api.intents(), api.plan()]);
      setIntents(i);
      setPlan(p);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the scheduler.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const habits = useMemo(
    () => intents.filter((i) => i.period_days !== null),
    [intents],
  );

  const windowTooSmall = to - from < minutes;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || windowTooSmall || saving) return;
    setSaving(true);
    setError(null);
    try {
      await createIntent({
        title: title.trim(),
        kind: "habit",
        priority,
        // The engine wants a total per period and a chunk size; the form
        // collects "how often" and "how long", which is the same information
        // in the units a person actually thinks in.
        minutes_per_period: times * minutes,
        period_days: 7,
        min_chunk_minutes: minutes,
        max_chunk_minutes: minutes,
        max_per_day: 1,
        window_start_min: from,
        window_end_min: to,
      });
      setTitle("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save that habit.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[900px] px-6 py-8">
        <header className="mb-7">
          <h1 className="text-[26px] font-semibold tracking-tight-optical">Habits</h1>
          <p className="mt-0.5 text-[13px] text-fg-muted">
            Recurring routines the scheduler places for you, and moves when a meeting lands
            on one.
          </p>
        </header>

        {error && (
          <p className="mb-5 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-[13px] text-danger">
            {error}
          </p>
        )}

        <form
          onSubmit={save}
          className="mb-7 overflow-hidden rounded-card border bg-surface shadow-sm"
        >
          <div className="border-b px-5 py-4">
            <label htmlFor="habit-title" className="mb-1.5 block text-[12px] font-medium text-fg-muted">
              What is the routine?
            </label>
            <input
              id="habit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Gym, deep work, lunch…"
              className="h-10 w-full rounded-md border bg-bg px-3 text-[14px] outline-none transition-colors focus:border-accent"
            />
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {PRESETS.map((preset) => (
                <button
                  key={preset.title}
                  type="button"
                  onClick={() => {
                    setTitle(preset.title);
                    setTimes(preset.times);
                    setMinutes(preset.minutes);
                    setFrom(preset.from);
                    setTo(preset.to);
                    setPriority(preset.priority as Priority);
                  }}
                  className="rounded-full border bg-bg px-3 py-1 text-[12px] text-fg-muted transition-colors duration-150 hover:border-accent hover:text-accent"
                >
                  {preset.title}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 px-5 py-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="How often" hint="times a week">
              <input
                type="number"
                min={1}
                max={14}
                value={times}
                onChange={(e) => setTimes(Math.max(1, Number(e.target.value)))}
                className="tabular h-9 w-full rounded-md border bg-bg px-3 text-[14px] outline-none focus:border-accent"
              />
            </Field>
            <Field label="How long" hint="minutes each">
              <select
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
                className="tabular h-9 w-full rounded-md border bg-bg px-3 text-[14px] outline-none focus:border-accent"
              >
                {[15, 30, 45, 60, 90, 120].map((m) => (
                  <option key={m} value={m}>
                    {m} min
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Between" hint="earliest">
              <input
                type="time"
                value={clock(from)}
                onChange={(e) => setFrom(toMinutes(e.target.value))}
                className="tabular h-9 w-full rounded-md border bg-bg px-3 text-[14px] outline-none focus:border-accent"
              />
            </Field>
            <Field label="And" hint="latest">
              <input
                type="time"
                value={clock(to)}
                onChange={(e) => setTo(toMinutes(e.target.value))}
                className="tabular h-9 w-full rounded-md border bg-bg px-3 text-[14px] outline-none focus:border-accent"
              />
            </Field>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-sunk px-5 py-3">
            <div className="flex items-center gap-1.5">
              {([1, 2, 3, 4] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriority(p)}
                  aria-pressed={priority === p}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] transition-colors duration-150 ${
                    priority === p ? "bg-surface shadow-sm" : "text-fg-muted hover:bg-surface/60"
                  }`}
                >
                  <span
                    className="h-3 w-[3px] rounded-sm"
                    style={{ background: PRIORITY_TINT[p] }}
                    aria-hidden
                  />
                  {PRIORITY_NAME[p]}
                </button>
              ))}
            </div>
            <button
              type="submit"
              disabled={!title.trim() || windowTooSmall || saving}
              className="h-9 rounded-md bg-accent px-4 text-[13px] font-medium text-on-accent transition-colors duration-150 hover:bg-accent-hover disabled:opacity-40"
            >
              {saving ? "Scheduling…" : "Add habit"}
            </button>
          </div>

          {/* Caught here rather than as a 422 after submit — the user can see
              the window is too short before they commit to it. */}
          {windowTooSmall && (
            <p className="border-t bg-danger/5 px-5 py-2.5 text-[12px] text-danger">
              That window is {formatDuration(Math.max(0, to - from))} long but each session needs{" "}
              {formatDuration(minutes)}. Widen it, or shorten the session.
            </p>
          )}
        </form>

        <h2 className="mb-3 text-[12px] font-medium uppercase tracking-wide text-fg-muted">
          Active routines
        </h2>

        {habits.length === 0 ? (
          <p className="rounded-card border bg-surface px-6 py-10 text-center text-[13px] text-fg-muted shadow-sm">
            No routines yet. Add one above, or press ⌘K and just describe it.
          </p>
        ) : (
          <ul className="space-y-2">
            {habits.map((habit) => {
              const blocks = plan?.blocks.filter((b) => b.intent_id === habit.id) ?? [];
              // "N x a week" is only true when every session is the same length.
              // For a goal with a range (90-120m), a count is a guess — state the
              // weekly total and the block range instead of inventing a number.
              const fixed = habit.min_chunk_minutes === habit.max_chunk_minutes;
              const cadence = fixed
                ? `${Math.round(habit.minutes_per_period / habit.min_chunk_minutes)}× a week · ${formatDuration(habit.min_chunk_minutes)} each`
                : `${formatDuration(habit.minutes_per_period)} a week · ${formatDuration(habit.min_chunk_minutes)}–${formatDuration(habit.max_chunk_minutes)} blocks`;
              return (
                <li
                  key={habit.id}
                  className="group flex items-center gap-3.5 rounded-card border bg-surface px-4 py-3.5 shadow-sm"
                >
                  <span
                    className="h-9 w-[3px] shrink-0 rounded-full"
                    style={{ background: PRIORITY_TINT[habit.priority as Priority] }}
                    aria-hidden
                  />
                  <span className="shrink-0 text-fg-subtle">
                    <Glyph kind={habit.kind} size={16} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14.5px] font-medium">{habit.title}</div>
                    <div className="tabular mt-0.5 text-[12px] text-fg-muted">
                      {cadence} · {blocks.length} placed
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      await api.remove(habit.id);
                      await load();
                    }}
                    aria-label={`Remove ${habit.title}`}
                    className="h-8 w-8 shrink-0 rounded-md text-fg-subtle opacity-0 transition-all duration-150 hover:bg-sunk hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </Shell>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-medium text-fg-muted">
        {label} <span className="font-normal text-fg-subtle">· {hint}</span>
      </span>
      {children}
    </label>
  );
}
