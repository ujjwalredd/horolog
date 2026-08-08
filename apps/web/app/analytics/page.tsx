"use client";

import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/app/components/Shell";
import { analytics, formatDuration, type Analytics } from "@/app/lib/api";

/* Categorical palette for the two-series load chart.
 *
 * Validated with the dataviz validator against the light surface — not chosen
 * by eye: lightness band PASS, chroma floor PASS, CVD separation ΔE 31.0
 * (protan) / 32.8 (tritan), normal-vision ΔE 37.2, contrast ≥ 3:1. The obvious
 * choice — accent plus a neutral gray for meetings — failed both the chroma
 * floor (it reads as absent data rather than a series) and 3:1 contrast.
 *
 * Warm-against-cool also carries the product's meaning: indigo is what the
 * scheduler placed, orange is what other people put on you. */
const SERIES = {
  scheduled: "#4F46E5",
  meetings: "#D95926",
} as const;

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

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
      <main className="mx-auto max-w-[1000px] px-6 py-8">
        <header className="mb-7">
          <h1 className="text-[26px] font-semibold tracking-tight-optical">Analytics</h1>
          <p className="mt-0.5 text-[13px] text-fg-muted">
            {data
              ? `Across the next ${data.horizon_days} days`
              : "Reading the plan…"}
          </p>
        </header>

        {error && (
          <p className="mb-5 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-[13px] text-danger">
            {error}
          </p>
        )}

        {data && (
          <>
            {/* Hero numbers are stat tiles, not charts — a single magnitude
                has no shape worth plotting. */}
            <section className="mb-6 grid gap-px overflow-hidden rounded-card border bg-line sm:grid-cols-2 lg:grid-cols-4">
              <Stat
                value={formatDuration(data.focus_minutes)}
                label="Deep-work time"
                note="in blocks of an hour or more"
              />
              <Stat
                value={`${Math.round(data.meeting_load * 100)}%`}
                label="Meeting load"
                note={`${formatDuration(data.meeting_minutes)} of your open hours`}
                warn={data.meeting_load > 0.4}
              />
              <Stat
                value={formatDuration(Math.round(data.fragmentation))}
                label="Average block"
                note="longer is better for focus"
                warn={data.fragmentation > 0 && data.fragmentation < 45}
              />
              <Stat
                value={
                  data.unmet_minutes ? formatDuration(data.unmet_minutes) : "Nothing"
                }
                label="Did not fit"
                note={data.unmet_minutes ? "your week is over-subscribed" : "everything is placed"}
                warn={data.unmet_minutes > 0}
              />
            </section>

            <section className="mb-6 rounded-card border bg-surface p-5 shadow-sm">
              <div className="mb-1 flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="text-[15px] font-medium">Where the days go</h2>
                {/* Legend is always present for two series — identity must
                    never rest on colour alone. */}
                <div className="flex items-center gap-4">
                  <LegendKey color={SERIES.scheduled} label="Scheduled work" />
                  <LegendKey color={SERIES.meetings} label="Meetings" />
                </div>
              </div>
              <p className="mb-5 text-[12.5px] text-fg-muted">
                Total committed hours per day, and the longest unbroken stretch left in each.
              </p>
              <DayChart data={data} />
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <section className="rounded-card border bg-surface p-5 shadow-sm">
                <h2 className="text-[15px] font-medium">Time by kind</h2>
                <p className="mb-5 mt-1 text-[12.5px] text-fg-muted">
                  Every bar is labelled, so shade carries magnitude rather than identity.
                </p>
                <Breakdown rows={data.by_kind} />
              </section>

              <section className="rounded-card border bg-surface p-5 shadow-sm">
                <h2 className="text-[15px] font-medium">Time by priority</h2>
                <p className="mb-5 mt-1 text-[12.5px] text-fg-muted">
                  A week where P4 outweighs P1 is a week that drifted.
                </p>
                <Breakdown rows={data.by_priority} />
              </section>
            </div>

            {data.after_hours_minutes > 0 && (
              <section className="mt-6 rounded-card border bg-surface p-5 shadow-sm">
                <h2 className="text-[15px] font-medium">Outside your hours</h2>
                <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
                  <span className="tabular text-fg">
                    {formatDuration(data.after_hours_minutes)}
                  </span>{" "}
                  of meetings fall outside your working day. The scheduler never puts work
                  there — this is time other people booked.
                </p>
              </section>
            )}
          </>
        )}
      </main>
    </Shell>
  );
}

function Stat({
  value,
  label,
  note,
  warn = false,
}: {
  value: string;
  label: string;
  note: string;
  warn?: boolean;
}) {
  return (
    <div className="bg-surface px-5 py-5">
      {/* Value in ink, never in a series colour. */}
      <div className={`tabular text-[26px] font-semibold leading-none ${warn ? "text-danger" : ""}`}>
        {value}
      </div>
      <div className="mt-2 text-[13px]">{label}</div>
      <div className="mt-0.5 text-[11.5px] text-fg-muted">{note}</div>
    </div>
  );
}

function LegendKey({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11.5px] text-fg-muted">
      <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}

/** Stacked load per day.
 *
 *  CSS rather than SVG: these are rectangles anchored to a baseline, and the
 *  browser's own layout does that correctly at every width with no viewBox
 *  arithmetic. A 2px surface gap separates the two stacked segments so the
 *  boundary survives both greyscale printing and colour-vision deficiency.
 */
function DayChart({ data }: { data: Analytics }) {
  const days = data.days.slice(0, 14);
  const ceiling = Math.max(
    data.window_minutes_per_day,
    ...days.map((d) => d.scheduled_minutes + d.meeting_minutes),
  );
  const origin = new Date();

  return (
    <div>
      <div className="flex items-end gap-2" style={{ height: 168 }}>
        {days.map((day) => {
          const date = new Date(origin);
          date.setDate(origin.getDate() + day.day);
          const total = day.scheduled_minutes + day.meeting_minutes;
          const scheduledH = (day.scheduled_minutes / ceiling) * 148;
          const meetingsH = (day.meeting_minutes / ceiling) * 148;

          return (
            <div key={day.day} className="group relative flex flex-1 flex-col items-center gap-1.5">
              <div className="relative flex w-full max-w-[34px] flex-col justify-end" style={{ height: 148 }}>
                {/* Tooltip: a chart in HTML is interactive by default. */}
                <div className="pointer-events-none absolute -top-1 left-1/2 z-20 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border bg-surface px-2.5 py-1.5 text-left shadow-pop group-hover:block">
                  <div className="text-[11px] font-medium">
                    {DAY_NAMES[date.getDay()]} {date.getDate()}
                  </div>
                  <div className="tabular mt-0.5 text-[10.5px] text-fg-muted">
                    {formatDuration(day.scheduled_minutes)} work ·{" "}
                    {formatDuration(day.meeting_minutes)} meetings
                  </div>
                  <div className="tabular text-[10.5px] text-fg-muted">
                    longest free run {formatDuration(day.longest_free_run_minutes)}
                  </div>
                </div>

                {meetingsH > 0 && (
                  <div
                    // Rounded only at the data end, and only when it is the top
                    // of the stack; a rounded join reads as two separate bars.
                    className="w-full rounded-t-[4px]"
                    style={{
                      height: Math.max(2, meetingsH),
                      background: SERIES.meetings,
                      marginBottom: scheduledH > 0 ? 2 : 0,
                    }}
                  />
                )}
                {scheduledH > 0 && (
                  <div
                    className={meetingsH > 0 ? "w-full" : "w-full rounded-t-[4px]"}
                    style={{ height: Math.max(2, scheduledH), background: SERIES.scheduled }}
                  />
                )}
                {total === 0 && <div className="w-full rounded-[3px] bg-sunk" style={{ height: 3 }} />}
              </div>

              <span className="tabular text-[10px] text-fg-muted">
                {DAY_NAMES[date.getDay()]}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 border-t pt-2.5 text-[11px] text-fg-muted">
        Baseline is your {formatDuration(data.window_minutes_per_day)} working day.
      </div>
    </div>
  );
}

/** Magnitude breakdown.
 *
 *  Every row is directly labelled, so colour is free to encode magnitude
 *  instead of identity — which is what lets this stay inside the product's
 *  single accent hue without failing a categorical separation check.
 */
function Breakdown({ rows }: { rows: Analytics["by_kind"] }) {
  if (!rows.length) {
    return <p className="text-[13px] text-fg-muted">Nothing scheduled yet.</p>;
  }
  const top = rows[0]!.minutes;
  return (
    <ul className="space-y-2.5">
      {rows.map((row, i) => (
        <li key={row.label} className="group">
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="text-[13px] capitalize">{row.label}</span>
            <span className="tabular text-[12px] text-fg-muted">
              {formatDuration(row.minutes)}
              <span className="ml-2 text-fg-subtle">{Math.round(row.share * 100)}%</span>
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-[3px] bg-sunk">
            <div
              className="h-full rounded-[3px] transition-[width] duration-300"
              style={{
                width: `${Math.max(2, (row.minutes / top) * 100)}%`,
                // Sequential: one hue, dark to light with rank.
                background: `color-mix(in srgb, ${SERIES.scheduled} ${
                  100 - i * 14
                }%, var(--color-line))`,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
