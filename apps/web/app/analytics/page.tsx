"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Shell } from "@/app/components/Shell";
import { Skeleton } from "@/app/components/Skeleton";
import { analytics, formatDuration, type Analytics } from "@/app/lib/api";
import { Clock } from "lucide-react";

const SERIES = {
  scheduled: "#6366F1",
  meetings: "#F97316",
} as const;

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Ultra-Luxury Productivity Analytics Page.
 *  Uses CVD-validated colors, stat tiles, stacked load charts, and kind/priority breakdowns.
 */
export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await analytics.get());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load analytics.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[1020px] px-6 py-8">
        <header className="mb-8">
          <h1 className="text-[28px] font-bold text-fg">Productivity Analytics</h1>
          <p className="mt-1 text-[13.5px] text-fg-muted">
            {data ? `Measured across your ${data.horizon_days}-day horizon` : "Reading the plan..."}
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-card border border-red-200 bg-red-50/70 p-4 text-[13.5px] text-danger shadow-xs">
            {error}
          </div>
        )}

        {!data && !error && <AnalyticsSkeleton />}

        {data && (
          <>
            {/* Stat Cards */}
            <section className="mb-7 grid gap-px overflow-hidden rounded-card border border-black/[0.08] bg-line sm:grid-cols-2 lg:grid-cols-4 shadow-sm">
              <Stat
                value={data.focus_minutes}
                format={(n) => formatDuration(Math.round(n))}
                label="Deep-work time"
                note="blocks ≥ 1 hour"
              />
              <Stat
                value={data.meeting_load * 100}
                format={(n) => `${Math.round(n)}%`}
                label="Meeting load"
                note={`${formatDuration(data.meeting_minutes)} of open hours`}
                warn={data.meeting_load > 0.4}
                sparkline={data.days.slice(0, 14).map((d) => d.meeting_minutes)}
              />
              <Stat
                value={data.fragmentation}
                format={(n) => formatDuration(Math.round(n))}
                label="Average block"
                note="longer is better for focus"
                warn={data.fragmentation > 0 && data.fragmentation < 45}
              />
              <Stat
                value={data.unmet_minutes}
                format={(n) => (n > 0 ? formatDuration(Math.round(n)) : "0m")}
                label="Unmet demand"
                note={data.unmet_minutes ? "schedule oversubscribed" : "100% placed"}
                warn={data.unmet_minutes > 0}
              />
            </section>

            {/* Main Day Load Chart */}
            <section className="mb-7 rounded-card border border-black/[0.08] bg-surface p-6 shadow-sm">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
                <div>
                  <h2 className="text-[17px] font-bold text-fg">Where the Days Go</h2>
                  <p className="mt-0.5 text-[13px] text-fg-muted">
                    Committed hours per day and unbroken focus gaps.
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <LegendKey color={SERIES.scheduled} label="Scheduled Work" />
                  <LegendKey color={SERIES.meetings} label="Meetings" />
                </div>
              </div>
              <div className="mt-6">
                <DayChart data={data} />
              </div>
            </section>

            {/* Breakdown Grids */}
            <div className="grid gap-6 lg:grid-cols-2">
              <section className="rounded-card border border-black/[0.08] bg-surface p-6 shadow-sm">
                <h2 className="text-[16px] font-bold text-fg">Time by Kind</h2>
                <p className="mb-5 mt-1 text-[13px] text-fg-muted">Distribution across task types.</p>
                <Breakdown rows={data.by_kind} />
              </section>

              <section className="rounded-card border border-black/[0.08] bg-surface p-6 shadow-sm">
                <h2 className="text-[16px] font-bold text-fg">Time by Priority</h2>
                <p className="mb-5 mt-1 text-[13px] text-fg-muted">Priority tier balance across the week.</p>
                <Breakdown rows={data.by_priority} />
              </section>
            </div>

            {data.after_hours_minutes > 0 && (
              <section className="mt-6 rounded-card border border-black/[0.08] bg-surface p-5 shadow-sm">
                <div className="flex items-center gap-2 text-[15px] font-bold text-fg">
                  <Clock size={16} className="text-amber-500" />
                  <span>After-Hours Meetings</span>
                </div>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-fg-muted">
                  <span className="tabular font-semibold text-fg">{formatDuration(data.after_hours_minutes)}</span> of meetings fall outside your configured workday window.
                </p>
              </section>
            )}
          </>
        )}
      </main>
    </Shell>
  );
}

/** Animates toward `target`, easing out over `durationMs` — skipped entirely
 *  under prefers-reduced-motion, which jumps straight to the final value.
 *
 *  Anchors each new animation to the value actually on screen right now
 *  (`shown`, updated every tick), not to the previous `target` — two
 *  re-solves landing within one `durationMs` of each other would otherwise
 *  make the number visibly jump to the stale midpoint before continuing. */
function useCountUp(target: number, durationMs = 400): number {
  const [display, setDisplay] = useState(target);
  const shown = useRef(target);

  useEffect(() => {
    const start = shown.current;
    if (start === target) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      shown.current = target;
      setDisplay(target);
      return;
    }
    const startTime = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - startTime) / durationMs);
      const eased = 1 - (1 - t) ** 3; // ease-out-cubic
      const value = start + (target - start) * eased;
      shown.current = value;
      setDisplay(value);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs]);

  return display;
}

function Stat({
  value,
  format,
  label,
  note,
  warn = false,
  sparkline,
}: {
  value: number;
  format: (n: number) => string;
  label: string;
  note: string;
  warn?: boolean;
  sparkline?: number[];
}) {
  const animated = useCountUp(value);
  return (
    <div className="bg-surface p-5">
      <div className={`tabular text-[28px] font-bold leading-none ${warn ? "text-danger" : "text-fg"}`}>
        {format(animated)}
      </div>
      <div className="mt-2.5 text-[13.5px] font-semibold text-fg">{label}</div>
      <div className="mt-0.5 text-[11.5px] font-medium text-fg-muted">{note}</div>
      {sparkline && sparkline.length > 1 && <Sparkline values={sparkline} />}
    </div>
  );
}

/** A minimal trend line — only ever passed data the API actually provides
 *  per-day; never fabricated for stats without a real series behind them. */
function Sparkline({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  const w = 100;
  const h = 22;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / max) * h}`)
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="mt-2.5 h-[22px] w-full text-accent/50"
      aria-hidden
    >
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

/** Matches the real layout's shape (4 stat cells, the chart, two breakdown
 *  panels) so the page doesn't go blank between mount and first data —
 *  `animate-pulse` is already neutralised under prefers-reduced-motion by
 *  the global rule in globals.css. */
function AnalyticsSkeleton() {
  return (
    <div aria-hidden>
      <section className="mb-7 grid gap-px overflow-hidden rounded-card border border-black/[0.08] bg-line sm:grid-cols-2 lg:grid-cols-4 shadow-sm">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2.5 bg-surface p-5">
            <Skeleton className="h-7 w-16" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-28" />
          </div>
        ))}
      </section>
      <section className="mb-7 h-[268px] rounded-card border border-black/[0.08] bg-surface shadow-sm">
        <Skeleton className="h-full w-full rounded-card" />
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-[220px] rounded-card border border-black/[0.08] shadow-sm" />
        <Skeleton className="h-[220px] rounded-card border border-black/[0.08] shadow-sm" />
      </div>
    </div>
  );
}

function LegendKey({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-2 text-[12px] font-semibold text-fg-muted">
      <span className="h-3 w-3 rounded-md" style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}

function DayChart({ data }: { data: Analytics }) {
  const days = data.days.slice(0, 14);
  const ceiling = Math.max(
    data.window_minutes_per_day,
    ...days.map((d) => d.scheduled_minutes + d.meeting_minutes),
  );
  const origin = new Date();

  return (
    <div>
      <div className="flex items-end gap-2.5" style={{ height: 180 }}>
        {days.map((day) => {
          const date = new Date(origin);
          date.setDate(origin.getDate() + day.day);
          const total = day.scheduled_minutes + day.meeting_minutes;
          const scheduledH = (day.scheduled_minutes / ceiling) * 156;
          const meetingsH = (day.meeting_minutes / ceiling) * 156;

          return (
            <div key={day.day} className="group relative flex flex-1 flex-col items-center gap-2">
              <div className="relative flex w-full max-w-[36px] flex-col justify-end" style={{ height: 156 }}>
                {/* Tooltip */}
                <div className="pointer-events-none absolute -top-2 left-1/2 z-30 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-xl border border-black/10 bg-slate-900/90 px-3 py-2 text-left shadow-pop backdrop-blur-md group-hover:block">
                  <div className="text-[12px] font-bold text-white">
                    {DAY_NAMES[date.getDay()]} {date.getDate()}
                  </div>
                  <div className="tabular mt-1 text-[11px] text-slate-300">
                    {formatDuration(day.scheduled_minutes)} work · {formatDuration(day.meeting_minutes)} meetings
                  </div>
                  <div className="tabular text-[11px] text-slate-400">
                    free run: {formatDuration(day.longest_free_run_minutes)}
                  </div>
                </div>

                {meetingsH > 0 && (
                  <div
                    className="w-full rounded-t-md transition-[height] duration-300"
                    style={{
                      height: Math.max(3, meetingsH),
                      background: SERIES.meetings,
                      marginBottom: scheduledH > 0 ? 2 : 0,
                    }}
                  />
                )}
                {scheduledH > 0 && (
                  <div
                    className={meetingsH > 0 ? "w-full transition-[height] duration-300" : "w-full rounded-t-md transition-[height] duration-300"}
                    style={{ height: Math.max(3, scheduledH), background: SERIES.scheduled }}
                  />
                )}
                {total === 0 && <div className="w-full rounded-md bg-sunk" style={{ height: 4 }} />}
              </div>

              <span className="tabular text-[11px] font-semibold text-fg-muted">
                {DAY_NAMES[date.getDay()]}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-4 border-t border-black/[0.06] pt-3 text-[11.5px] font-medium text-fg-muted">
        Baseline: {formatDuration(data.window_minutes_per_day)} working day.
      </div>
    </div>
  );
}

function Breakdown({ rows }: { rows: Analytics["by_kind"] }) {
  if (!rows.length) {
    return <p className="text-[13.5px] text-fg-muted">Nothing scheduled yet.</p>;
  }
  const top = rows[0]!.minutes;
  return (
    <ul className="space-y-3.5">
      {rows.map((row, i) => (
        <li key={row.label} className="group">
          <div className="mb-1.5 flex items-baseline justify-between gap-3">
            <span className="text-[14px] font-semibold capitalize text-fg">{row.label}</span>
            <span className="tabular text-[12.5px] font-medium text-fg-muted">
              {formatDuration(row.minutes)}
              <span className="ml-2 text-indigo-600 font-semibold">{Math.round(row.share * 100)}%</span>
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-sunk">
            <div
              className="h-full rounded-full transition-[width] duration-300"
              style={{
                width: `${Math.max(3, (row.minutes / top) * 100)}%`,
                background: `color-mix(in srgb, ${SERIES.scheduled} ${100 - i * 14}%, var(--color-line))`,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
