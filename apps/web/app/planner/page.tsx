"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import { Grid, PRIORITY_LABEL, RULE } from "@/app/components/Grid";
import { Shell } from "@/app/components/Shell";
import { api, formatDuration, minutesBetween, type Plan } from "@/app/lib/api";
import { ChevronLeft, ChevronRight, Download, AlertTriangle, Info, Sparkles } from "lucide-react";

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
      <main className="mx-auto max-w-[1280px] px-6 py-8">
        {/* Header Bar */}
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

          {/* Actions & Segmented Control */}
          <div className="flex items-center gap-3">
            <div className="flex items-center rounded-xl border border-black/[0.08] bg-surface p-1 shadow-sm">
              <button
                type="button"
                onClick={() => setWeekOffset((w) => w - 1)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-sunk hover:text-fg"
                aria-label="Previous week"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                onClick={() => setWeekOffset(0)}
                disabled={weekOffset === 0}
                className="h-8 rounded-lg px-3 text-[13px] font-medium transition-colors hover:bg-sunk disabled:text-fg-subtle"
              >
                Today
              </button>
              <button
                type="button"
                onClick={() => setWeekOffset((w) => w + 1)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-sunk hover:text-fg"
                aria-label="Next week"
              >
                <ChevronRight size={16} />
              </button>
            </div>

            <a
              href="/api/plan.ics"
              className="inline-flex h-9.5 items-center gap-1.5 rounded-xl border border-black/[0.08] bg-surface px-4 text-[13px] font-semibold text-fg shadow-sm transition-all duration-150 hover:bg-sunk hover:shadow-md"
            >
              <Download size={14} className="text-fg-muted" />
              Export .ics
            </a>
          </div>
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

        <div className="grid gap-6 lg:grid-cols-[1fr_270px]">
          {/* Main Grid */}
          <section id="planner" aria-label="Week grid">
            <Grid
              days={days}
              blocks={plan?.blocks ?? []}
              busy={plan?.busy ?? []}
              selected={selected}
              onSelect={setSelected}
            />
          </section>

          {/* Right Sidebar Info Cards */}
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
