"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Grid } from "@/app/components/Grid";
import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import { Shell } from "@/app/components/Shell";
import { api, formatDuration, minutesBetween, type IntentKind, type Plan } from "@/app/lib/api";
import { ArrowRight } from "lucide-react";

function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

/** Live "today" view: a single-day timeline with a moving now-line, plus
 *  what's in progress and what's next. Complements Planner (week grid) and
 *  Analytics (aggregate stats) rather than duplicating either. */
export default function TimePage() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());

  const load = useCallback(async () => {
    try {
      setPlan(await api.plan());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the schedule.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const today = useMemo(() => new Date(), []);
  const todayKey = today.toISOString().slice(0, 10);

  const todaysBlocks = useMemo(
    () => (plan ? plan.blocks.filter((b) => dayKey(b.start) === todayKey) : []),
    [plan, todayKey],
  );

  const current = todaysBlocks.find((b) => b.start <= now.toISOString() && now.toISOString() < b.end);
  const next = todaysBlocks
    .filter((b) => b.start > now.toISOString())
    .sort((a, b) => a.start.localeCompare(b.start))[0];

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[1440px] px-6 py-8">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold text-fg">Time</h1>
            <p className="mt-1 text-[13.5px] text-fg-muted">
              {today.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}
            </p>
          </div>
          <div className="tabular text-[32px] font-semibold leading-none text-fg">
            {now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })}
          </div>
        </header>

        {error && (
          <div className="mb-6 rounded-card border border-red-200 bg-red-50/70 p-4 text-[13.5px] text-danger shadow-xs">
            {error}
          </div>
        )}

        <div className="mb-7 grid gap-4 sm:grid-cols-2">
          <StatusCard
            label="Right now"
            block={current}
            empty={plan ? "Nothing scheduled — this time is open." : "Reading the plan..."}
          />
          <StatusCard
            label="Up next"
            block={next}
            empty={plan ? "Nothing else scheduled for today." : "Reading the plan..."}
            untilNow={now}
          />
        </div>

        <Grid
          days={[today]}
          blocks={plan?.blocks ?? []}
          busy={plan?.busy ?? []}
          selected={selected}
          onSelect={setSelected}
        />
      </main>
    </Shell>
  );
}

function StatusCard({
  label,
  block,
  empty,
  untilNow,
}: {
  label: string;
  block: { title: string; kind: IntentKind; priority: number; start: string; end: string } | undefined;
  empty: string;
  untilNow?: Date;
}) {
  return (
    <div className="rounded-card border border-black/[0.08] bg-surface p-5 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">{label}</div>
      {block ? (
        <div className="mt-2 flex items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sunk text-fg">
            <Glyph kind={block.kind} size={15} />
          </span>
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold text-fg">{block.title}</div>
            <div className="tabular mt-0.5 flex items-center gap-1.5 text-[12px] text-fg-muted">
              <span>{KIND_LABEL[block.kind]}</span>
              <span>·</span>
              <span>
                {new Date(block.start).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                <ArrowRight size={10} className="mx-1 inline align-middle" />
                {new Date(block.end).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
              </span>
              {untilNow && (
                <>
                  <span>·</span>
                  <span>in {formatDuration(minutesBetween(untilNow.toISOString(), block.start))}</span>
                </>
              )}
            </div>
          </div>
        </div>
      ) : (
        <p className="mt-2.5 text-[13.5px] text-fg-muted">{empty}</p>
      )}
    </div>
  );
}
