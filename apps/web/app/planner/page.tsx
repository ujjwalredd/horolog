"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import { PRIORITY_LABEL, RULE } from "@/app/components/Grid";
import { Shell } from "@/app/components/Shell";
import { api, formatDuration, minutesBetween, type Plan, type Block, type Busy } from "@/app/lib/api";
import { EventManager, type Event } from "@/components/ui/event-manager";
import Link from "next/link";
import {
  Download,
  AlertTriangle,
  Sparkles,
  Command,
  Link2,
} from "lucide-react";

/** Map backend priority number to EventManager color values */
const PRIORITY_COLOR: Record<number, string> = {
  1: "blue",
  2: "purple",
  3: "green",
  4: "orange",
};

/** The default palette plus one extra: real external events are locked and
 *  need a colour no priority uses, so they read as visually distinct at a
 *  glance rather than as a fifth "normal" block. */
const COLORS = [
  { name: "Blue", value: "blue", bg: "bg-blue-500", text: "text-blue-700" },
  { name: "Green", value: "green", bg: "bg-green-500", text: "text-green-700" },
  { name: "Purple", value: "purple", bg: "bg-purple-500", text: "text-purple-700" },
  { name: "Orange", value: "orange", bg: "bg-orange-500", text: "text-orange-700" },
  { name: "Slate", value: "slate", bg: "bg-slate-500", text: "text-slate-700" },
];

const EXTERNAL_PREFIX = "external-";

function kindToCategory(kind: string): string {
  return kind.charAt(0).toUpperCase() + kind.slice(1);
}

/** Convert backend Block[] to EventManager Event[] */
function blocksToEvents(blocks: Block[]): Event[] {
  return blocks.map((block) => {
    const tags: string[] = [PRIORITY_LABEL[block.priority]];
    if (block.moved_from !== null && block.moved_from !== block.start) {
      tags.push("Moved");
    }
    if (block.energy) {
      tags.push(block.energy.charAt(0).toUpperCase() + block.energy.slice(1) + " Energy");
    }
    return {
      // Multiple chunks of the same occurrence (a long focus session split
      // into two sittings, say) share intent_id + occurrence — chunk has to
      // be part of the key too, or React sees duplicate ids and month view
      // (which lists several events per day cell) renders it visibly.
      id: `${block.intent_id}-${block.occurrence}-${block.chunk}`,
      title: block.title,
      description: `${KIND_LABEL[block.kind]} · Chunk ${block.chunk} · ${formatDuration(minutesBetween(block.start, block.end))}`,
      startTime: new Date(block.start),
      endTime: new Date(block.end),
      color: PRIORITY_COLOR[block.priority] || "green",
      category: kindToCategory(block.kind),
      tags,
    };
  });
}

/** Real, immovable commitments — meetings, decompression buffers, accepted
 *  bookings. Rendered read-only: nothing the solver placed may ever overlap
 *  these, and the planner has to show *why* rather than leave a silent gap. */
function busyToEvents(busy: Busy[]): Event[] {
  return busy.map((event, index) => ({
    id: `${EXTERNAL_PREFIX}${index}`,
    title: event.label || "Busy",
    description: `External · ${event.source}`,
    startTime: new Date(event.start),
    endTime: new Date(event.end),
    color: "slate",
    category: "External",
    tags: ["Locked"],
  }));
}

export default function Planner() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPlan(await api.plan());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the scheduler.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const scheduledMinutes = useMemo(
    () => plan?.blocks.reduce((sum, b) => sum + minutesBetween(b.start, b.end), 0) ?? 0,
    [plan],
  );
  const movedCount = useMemo(
    () =>
      plan?.blocks.filter((b) => b.moved_from !== null && b.moved_from !== b.start).length ?? 0,
    [plan],
  );

  const calendarEvents = useMemo(
    () => [...blocksToEvents(plan?.blocks ?? []), ...busyToEvents(plan?.busy ?? [])],
    [plan],
  );

  const handleEventCreate = useCallback(
    async (event: Omit<Event, "id">) => {
      try {
        const durationMinutes = Math.round(
          (event.endTime.getTime() - event.startTime.getTime()) / 60000,
        );
        const text = `${event.title} for ${durationMinutes} minutes`;
        await api.capture(text);
        await load();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Failed to create event.");
      }
    },
    [load],
  );

  const handleEventDelete = useCallback(
    async (id: string) => {
      if (id.startsWith(EXTERNAL_PREFIX)) {
        setError("That's a real calendar event, not one Horolog placed — remove it at the source and re-sync.");
        return;
      }
      try {
        // id is `${intent_id}-${occurrence}-${chunk}` — strip both trailing
        // numeric segments to recover the bare intent_id.
        const parts = id.split("-");
        const intentId = parts.length > 2 ? parts.slice(0, -2).join("-") : parts[0] ?? id;
        await api.remove(intentId);
        await load();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Failed to delete event.");
      }
    },
    [load],
  );

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[1440px] px-6 py-8">
        {/* Header */}
        <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold text-fg">Planner</h1>
            <p className="mt-1 text-[13.5px] text-fg-muted">
              {plan ? (
                <span className="inline-flex items-center gap-2">
                  <span className="font-semibold text-fg">{plan.blocks.length} blocks</span>
                  <span>·</span>
                  <span>{formatDuration(scheduledMinutes)} scheduled</span>
                  <span>·</span>
                  <span className="tabular text-accent font-medium">solved in {plan.solve_ms.toFixed(1)}ms</span>
                </span>
              ) : (
                "Loading schedule..."
              )}
            </p>
          </div>

          <a
            href="/api/plan.ics"
            className="inline-flex h-9.5 items-center gap-1.5 rounded-xl border border-black/[0.08] bg-surface px-4 text-[13px] font-semibold text-fg shadow-sm transition-all duration-150 hover:bg-sunk hover:shadow-md"
          >
            <Download size={14} className="text-fg-muted" />
            Export .ics
          </a>
        </header>

        {error && (
          <div className="mb-6 rounded-card border border-red-200/80 bg-red-50/60 p-4 shadow-sm">
            <div className="flex items-center gap-2 text-[13.5px] font-semibold text-danger">
              <AlertTriangle size={16} />
              <span>{error}</span>
            </div>
            <p className="mt-1 text-[12.5px] text-fg-muted">
              Ensure the backend API is running on port 8000.
            </p>
          </div>
        )}

        {plan && plan.blocks.length === 0 && plan.busy.length === 0 && (
          <div className="mb-6 rounded-card border border-black/[0.08] bg-surface p-5 shadow-sm">
            <h2 className="text-[14px] font-semibold text-fg">Nothing scheduled yet</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              A fresh install starts with an empty calendar on purpose — nothing is faked. Get a
              real week on the board with any of these:
            </p>
            <ul className="mt-3 space-y-2 text-[13px] text-fg-muted">
              <li className="flex items-center gap-2">
                <kbd className="tabular inline-flex items-center gap-0.5 rounded-md border border-black/[0.08] bg-sunk px-1.5 py-0.5 text-[10.5px] font-mono">
                  <Command size={10} />K
                </kbd>
                capture something in plain language, e.g. &ldquo;gym 3x a week, an hour each&rdquo;
              </li>
              <li className="flex items-center gap-2">
                <Link2 size={13} className="text-accent" />
                <Link href="/connect" className="font-medium text-accent hover:underline">
                  Connect a calendar
                </Link>
                {" "}to pull in what you already have
              </li>
              <li className="flex items-center gap-2">
                <span className="rounded-md border border-black/[0.08] bg-sunk px-1.5 py-0.5 font-mono text-[10.5px]">
                  npm run seed:demo
                </span>
                for a sample week, if you're just trying it out
              </li>
            </ul>
          </div>
        )}

        {/* Calendar + Sidebar */}
        <div className="grid gap-6 lg:grid-cols-[1fr_270px]">
          <section aria-label="Calendar view">
            <EventManager
              events={calendarEvents}
              onEventCreate={handleEventCreate}
              onEventDelete={handleEventDelete}
              categories={["Task", "Habit", "Focus", "Buffer", "Meeting", "External"]}
              availableTags={["Critical", "High", "Normal", "Low", "Moved", "Locked", "High Energy", "Medium Energy", "Low Energy"]}
              colors={COLORS}
              defaultView="month"
              className="min-h-[600px]"
            />
          </section>

          <aside className="space-y-4">
            {movedCount > 0 && (
              <Panel title="Shift Stability">
                <div className="flex items-start gap-2.5">
                  <Sparkles size={16} className="mt-0.5 shrink-0 text-accent" />
                  <p className="text-[13px] leading-relaxed text-fg-muted">
                    <span className="font-semibold text-fg">{movedCount} {movedCount === 1 ? "block" : "blocks"}</span> shifted to fit new commitments. All other tasks remained untouched.
                  </p>
                </div>
              </Panel>
            )}

            {plan && !plan.complete && (
              <Panel title="Unmet Demand">
                <ul className="space-y-3">
                  {plan.unmet.map((item) => (
                    <li key={`${item.intent_id}-${item.title}`} className="flex gap-2.5">
                      <span
                        className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                        style={{ background: RULE[item.priority] }}
                        aria-hidden
                      />
                      <div className="min-w-0">
                        <span className="block truncate text-[13px] font-semibold text-fg">{item.title}</span>
                        <span className="tabular text-[11.5px] text-danger font-medium">
                          {formatDuration(item.shortfall_minutes)} short · {PRIORITY_LABEL[item.priority]}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
                <p className="mt-3.5 border-t border-black/[0.06] pt-3 text-[12px] text-fg-muted">
                  Widen daily windows or lower priority to fit remaining demand.
                </p>
              </Panel>
            )}

            <Panel title="Legend">
              <ul className="space-y-2.5">
                {(["task", "habit", "focus", "buffer", "meeting"] as const).map((kind) => (
                  <li key={kind} className="flex items-center gap-2.5 text-[13px] text-fg font-medium">
                    <span className="text-accent">
                      <Glyph kind={kind} size={15} />
                    </span>
                    {KIND_LABEL[kind]}
                  </li>
                ))}
              </ul>
              <div className="mt-4 space-y-2.5 border-t border-black/[0.06] pt-3.5">
                {([1, 2, 3, 4] as const).map((priority) => (
                  <div key={priority} className="flex items-center gap-2.5 text-[12.5px] text-fg-muted font-medium">
                    <span
                      className="h-3.5 w-1 rounded-full"
                      style={{ background: RULE[priority] }}
                      aria-hidden
                    />
                    {PRIORITY_LABEL[priority]} Priority
                  </div>
                ))}
                <div className="flex items-center gap-2.5 pt-1 text-[12px] text-fg-muted">
                  <span
                    className="h-3.5 border-l-2 border-dashed"
                    style={{ borderColor: RULE[3] }}
                    aria-hidden
                  />
                  Moved block
                </div>
                <div className="flex items-center gap-2.5 text-[12px] text-fg-muted">
                  <span className="h-3.5 w-1 rounded-full bg-slate-300" aria-hidden />
                  Real calendar meeting
                </div>
              </div>
            </Panel>
          </aside>
        </div>
      </main>
    </Shell>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-card border border-black/[0.06] bg-surface p-4.5 shadow-sm">
      <h2 className="mb-3 text-[11px] font-semibold tracking-wider uppercase text-fg-muted">
        {title}
      </h2>
      {children}
    </div>
  );
}
