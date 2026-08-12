"use client";

import { useCallback, useEffect, useState } from "react";
import { Glyph } from "@/app/components/Glyph";
import { PriorityPicker } from "@/app/components/PriorityPicker";
import { Shell } from "@/app/components/Shell";
import { Skeleton } from "@/app/components/Skeleton";
import {
  PRIORITY_TINT,
  api,
  createIntent,
  formatDuration,
  type AttendeeBusy,
  type Intent,
  type Priority,
} from "@/app/lib/api";
import { Plus, Trash2, AlertTriangle, Video } from "lucide-react";

interface BusyRow {
  start: string;
  end: string;
  attendee: string;
}

const EMPTY_ROW: BusyRow = { start: "", end: "", attendee: "" };

/** Smart Meeting creation - the one intent kind whose scheduling engine
 *  (attendee free/busy intersection, `Intent.blocked_slots`) already exists
 *  and is tested server-side but had no way to reach it from the app. */
export default function Meetings() {
  const [intents, setIntents] = useState<Intent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState(30);
  const [priority, setPriority] = useState<Priority>(2);
  const [rows, setRows] = useState<BusyRow[]>([{ ...EMPTY_ROW }]);

  const load = useCallback(async () => {
    try {
      setIntents(await api.intents());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the scheduler.");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const meetings = intents.filter((i) => i.kind === "meeting");

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const attendee_busy: AttendeeBusy[] = rows
        .filter((r) => r.start && r.end)
        .map((r) => ({
          start: new Date(r.start).toISOString(),
          end: new Date(r.end).toISOString(),
          ...(r.attendee.trim() ? { attendee: r.attendee.trim() } : {}),
        }));

      await createIntent({
        title: title.trim(),
        kind: "meeting",
        priority,
        minutes_per_period: minutes,
        min_chunk_minutes: minutes,
        max_chunk_minutes: minutes,
        attendee_busy,
      });
      setTitle("");
      setRows([{ ...EMPTY_ROW }]);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save that meeting.");
    } finally {
      setSaving(false);
    }
  }

  function updateRow(index: number, patch: Partial<BusyRow>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[920px] px-6 py-8">
        <header className="mb-8">
          <h1 className="text-[28px] font-bold text-fg">Smart Meetings</h1>
          <p className="mt-1 text-[13.5px] text-fg-muted">
            Placed only where every attendee is free - their busy time never touches your own calendar.
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-card border border-red-200 bg-red-50/70 p-4 text-[13.5px] text-danger shadow-xs">
            {error}
          </div>
        )}

        <form
          onSubmit={save}
          className="mb-9 overflow-hidden rounded-card border border-black/[0.08] bg-surface shadow-sm transition-shadow hover:shadow-md"
        >
          <div className="grid gap-5 border-b border-black/[0.06] px-6 py-4.5 sm:grid-cols-3">
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-[12px] font-semibold tracking-wider uppercase text-fg-muted">
                Meeting Title
              </span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Weekly sync"
                className="h-11 w-full rounded-xl border border-black/[0.08] bg-bg px-4 text-[15px] font-medium outline-none transition-colors focus:border-accent"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[12px] font-semibold tracking-wider uppercase text-fg-muted">
                Duration
              </span>
              <select
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
                className="tabular h-11 w-full rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[14px] font-semibold outline-none focus:border-accent"
              >
                {[15, 30, 45, 60, 90, 120].map((m) => (
                  <option key={m} value={m}>
                    {m} min
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="border-b border-black/[0.06] px-6 py-4.5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[12px] font-semibold tracking-wider uppercase text-fg-muted">
                Attendee busy times
              </span>
              <button
                type="button"
                onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}
                className="inline-flex items-center gap-1 text-[12px] font-semibold text-accent hover:text-accent-hover"
              >
                <Plus size={13} />
                Add range
              </button>
            </div>
            <div className="space-y-2.5">
              {rows.map((row, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2">
                  <input
                    type="datetime-local"
                    value={row.start}
                    onChange={(e) => updateRow(i, { start: e.target.value })}
                    className="tabular h-10 min-w-0 flex-1 rounded-xl border border-black/[0.08] bg-bg px-3 text-[13px] font-medium outline-none focus:border-accent"
                  />
                  <input
                    type="datetime-local"
                    value={row.end}
                    onChange={(e) => updateRow(i, { end: e.target.value })}
                    className="tabular h-10 min-w-0 flex-1 rounded-xl border border-black/[0.08] bg-bg px-3 text-[13px] font-medium outline-none focus:border-accent"
                  />
                  <input
                    value={row.attendee}
                    onChange={(e) => updateRow(i, { attendee: e.target.value })}
                    placeholder="attendee (optional)"
                    className="h-10 w-36 rounded-xl border border-black/[0.08] bg-bg px-3 text-[13px] font-medium outline-none focus:border-accent"
                  />
                  <button
                    type="button"
                    onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
                    disabled={rows.length === 1}
                    aria-label="Remove range"
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-fg-subtle transition-colors hover:bg-red-50 hover:text-danger disabled:opacity-30"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
            {rows.every((r) => !r.start || !r.end) && (
              <div className="mt-3 flex items-center gap-2 text-[12.5px] font-medium text-fg-muted">
                <AlertTriangle size={14} />
                No busy ranges yet - the meeting will schedule against your own calendar only.
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-black/[0.06] bg-sunk/40 px-6 py-3.5">
            <PriorityPicker value={priority} onChange={setPriority} />
            <button
              type="submit"
              disabled={!title.trim() || saving}
              className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-accent px-5 text-[13.5px] font-semibold text-on-accent shadow-sm transition-all duration-150 hover:bg-accent-hover hover:shadow-md disabled:opacity-40"
            >
              <Plus size={16} />
              {saving ? "Scheduling..." : "Add Meeting"}
            </button>
          </div>
        </form>

        <h2 className="mb-3.5 text-[12px] font-semibold tracking-wider uppercase text-fg-muted">
          Smart Meetings {loaded ? `(${meetings.length})` : ""}
        </h2>

        {!loaded ? (
          <ul aria-hidden className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <li
                key={i}
                className="flex items-center gap-4 rounded-card border border-black/[0.06] bg-surface p-4.5 shadow-sm"
              >
                <Skeleton className="h-10 w-1 shrink-0 rounded-full" />
                <Skeleton className="h-[18px] w-[18px] shrink-0 rounded-full" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </li>
            ))}
          </ul>
        ) : meetings.length === 0 ? (
          <div className="rounded-card border border-black/[0.06] bg-surface p-10 text-center shadow-sm">
            <p className="text-[14px] font-semibold text-fg">No smart meetings yet</p>
            <p className="mt-1 text-[13px] text-fg-muted">Configure one above, with or without attendee ranges.</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {meetings.map((meeting) => {
              const ranges = meeting.blocked_slots?.length ?? 0;
              return (
                <li
                  key={meeting.id}
                  className="group flex items-center gap-4 rounded-card border border-black/[0.06] bg-surface p-4.5 shadow-sm transition-all duration-200 hover:shadow-md"
                >
                  <span
                    className="h-10 w-1 shrink-0 rounded-full"
                    style={{ background: PRIORITY_TINT[meeting.priority as Priority] }}
                    aria-hidden
                  />
                  <span className="shrink-0 text-accent">
                    <Glyph kind={meeting.kind} size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[15px] font-semibold text-fg">{meeting.title}</div>
                    <div className="tabular mt-1 text-[12.5px] font-medium text-fg-muted">
                      {formatDuration(meeting.minutes_per_period)} ·{" "}
                      {ranges > 0 ? `${ranges} attendee range${ranges === 1 ? "" : "s"} avoided` : "no attendee ranges"}
                    </div>
                    {meeting.zoom_join_url && (
                      <a
                        href={meeting.zoom_join_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1.5 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-accent hover:underline"
                      >
                        <Video size={13} />
                        Join Zoom
                      </a>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      await api.remove(meeting.id);
                      await load();
                    }}
                    aria-label={`Remove ${meeting.title}`}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-fg-subtle opacity-0 transition-all duration-150 hover:bg-red-50 hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 size={15} />
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
