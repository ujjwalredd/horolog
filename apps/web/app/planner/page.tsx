"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import { Grid, PRIORITY_LABEL, RULE } from "@/app/components/Grid";
import { Shell } from "@/app/components/Shell";
import { api, formatDuration, minutesBetween, type Plan } from "@/app/lib/api";

const VISIBLE_DAYS = 7;

export default function Planner() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [weekOffset, setWeekOffset] = useState(0);

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

  const days = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() + weekOffset * VISIBLE_DAYS);
    return Array.from({ length: VISIBLE_DAYS }, (_, i) => {
      const day = new Date(start);
      day.setDate(start.getDate() + i);
      return day;
    });
  }, [weekOffset]);

  const scheduledMinutes = useMemo(
    () => plan?.blocks.reduce((sum, b) => sum + minutesBetween(b.start, b.end), 0) ?? 0,
    [plan],
  );
  const movedCount = useMemo(
    () =>
      plan?.blocks.filter((b) => b.moved_from !== null && b.moved_from !== b.start).length ?? 0,
    [plan],
  );

  return (
    <Shell onPlanChange={load}>
    <main className="mx-auto max-w-[1240px] px-6 py-8">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-semibold">Planner</h1>
          <p className="mt-0.5 text-[13px] text-fg-muted">
            {plan
              ? `${plan.blocks.length} blocks · ${formatDuration(scheduledMinutes)} scheduled · planned in ${plan.solve_ms.toFixed(0)}ms`
              : "Loading…"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-md border bg-surface shadow-sm">
            <button
              type="button"
              onClick={() => setWeekOffset((w) => w - 1)}
              className="h-9 w-9 text-fg-muted transition-colors duration-150 hover:bg-sunk hover:text-fg"
              aria-label="Previous week"
            >
              ‹
            </button>
            <button
              type="button"
              onClick={() => setWeekOffset(0)}
              disabled={weekOffset === 0}
              className="h-9 border-x px-3 text-[13px] transition-colors duration-150 hover:bg-sunk disabled:text-fg-muted"
            >
              Today
            </button>
            <button
              type="button"
              onClick={() => setWeekOffset((w) => w + 1)}
              className="h-9 w-9 text-fg-muted transition-colors duration-150 hover:bg-sunk hover:text-fg"
              aria-label="Next week"
            >
              ›
            </button>
          </div>

          <a
            href="/api/plan.ics"
            className="flex h-9 items-center rounded-md border bg-surface px-3.5 text-[13px] font-medium shadow-sm transition-colors duration-150 hover:bg-sunk"
          >
            Export
          </a>
        </div>
      </header>

      {error && (
        <div className="mb-5 rounded-card border border-danger/30 bg-danger/5 px-4 py-3">
          <p className="text-[13px] text-danger">{error}</p>
          <p className="mt-1 text-[12px] text-fg-muted">
            Check that the API is running on port 8000, then reload.
          </p>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_268px]">
        <section id="planner" aria-label="Week grid">
          <Grid
            days={days}
            blocks={plan?.blocks ?? []}
            busy={plan?.busy ?? []}
            selected={selected}
            onSelect={setSelected}
          />
        </section>

        <aside className="space-y-4">
          {movedCount > 0 && (
            <Panel title="Moved this replan">
              <p className="text-[13px] text-fg-muted">
                {movedCount} {movedCount === 1 ? "block" : "blocks"} shifted. Everything
                else stayed exactly where it was.
              </p>
            </Panel>
          )}

          {plan && !plan.complete && (
            <Panel title="Did not fit">
              <ul className="space-y-2.5">
                {plan.unmet.map((item) => (
                  <li key={`${item.intent_id}-${item.title}`} className="flex gap-2">
                    <span
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: RULE[item.priority] }}
                      aria-hidden
                    />
                    <span className="min-w-0">
                      <span className="block truncate text-[13px]">{item.title}</span>
                      <span className="tabular text-[11px] text-fg-muted">
                        {formatDuration(item.shortfall_minutes)} short ·{" "}
                        {PRIORITY_LABEL[item.priority]}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 border-t pt-3 text-[12px] text-fg-muted">
                Your week is over-subscribed. Drop something, or widen a window.
              </p>
            </Panel>
          )}

          <Panel title="Legend">
            <ul className="space-y-2">
              {(["task", "habit", "focus", "buffer", "meeting"] as const).map((kind) => (
                <li key={kind} className="flex items-center gap-2 text-[13px] text-fg-muted">
                  <span className="text-fg-subtle">
                    <Glyph kind={kind} size={14} />
                  </span>
                  {KIND_LABEL[kind]}
                </li>
              ))}
            </ul>
            <div className="mt-3 space-y-2 border-t pt-3">
              {([1, 2, 3, 4] as const).map((priority) => (
                <div key={priority} className="flex items-center gap-2 text-[12px] text-fg-muted">
                  <span
                    className="h-3.5 w-[3px] rounded-sm"
                    style={{ background: RULE[priority] }}
                    aria-hidden
                  />
                  {PRIORITY_LABEL[priority]}
                </div>
              ))}
              <div className="flex items-center gap-2 pt-1 text-[12px] text-fg-muted">
                <span
                  className="h-3.5 border-l-2 border-dashed"
                  style={{ borderColor: RULE[3] }}
                  aria-hidden
                />
                Moved since last plan
              </div>
              <div className="flex items-center gap-2 text-[12px] text-fg-muted">
                <span
                  className="h-3.5 w-[3px] rounded-sm bg-line-strong"
                  aria-hidden
                />
                Your real meetings — never moved
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
    <div className="rounded-card border bg-surface p-4 shadow-sm">
      <h2 className="mb-3 text-[11px] font-medium uppercase tracking-wide text-fg-muted">
        {title}
      </h2>
      {children}
    </div>
  );
}
