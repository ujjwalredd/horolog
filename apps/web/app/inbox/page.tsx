"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import { Shell } from "@/app/components/Shell";
import {
  PRIORITY_NAME,
  PRIORITY_TINT,
  api,
  formatDuration,
  minutesBetween,
  type Intent,
  type Plan,
  type Priority,
} from "@/app/lib/api";
import { Trash2, AlertCircle, Clock, CheckCircle, Sparkles } from "lucide-react";

/** Ultra-Luxury Task Inbox View for Horolog.
 *  Displays all scheduling intents, their placed time progress bars, and unmet demand callouts.
 */
export default function Inbox() {
  const [intents, setIntents] = useState<Intent[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

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

  const rows = useMemo(() => {
    const blocks = plan?.blocks ?? [];
    const shortfall = new Map(plan?.unmet.map((u) => [u.intent_id, u.shortfall_minutes]) ?? []);
    return intents
      .map((intent) => {
        const mine = blocks
          .filter((b) => b.intent_id === intent.id)
          .sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
        const scheduled = mine.reduce((sum, b) => sum + minutesBetween(b.start, b.end), 0);
        return {
          intent,
          blocks: mine,
          scheduled,
          short: shortfall.get(intent.id) ?? 0,
          next: mine[0] ?? null,
          percent: Math.min(100, Math.round((scheduled / intent.minutes_per_period) * 100)),
        };
      })
      .sort((a, b) => {
        if (a.short !== b.short) return b.short - a.short;
        if (a.intent.priority !== b.intent.priority) return a.intent.priority - b.intent.priority;
        return (a.next ? Date.parse(a.next.start) : Infinity) -
          (b.next ? Date.parse(b.next.start) : Infinity);
      });
  }, [intents, plan]);

  async function remove(id: string) {
    setBusy(id);
    try {
      await api.remove(id);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not remove that.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[920px] px-6 py-8">
        <header className="mb-8 flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold text-fg">Task Inbox</h1>
            <p className="mt-1 text-[13.5px] text-fg-muted">
              {plan ? (
                <>
                  {rows.length} {rows.length === 1 ? "intent" : "intents"} ·{" "}
                  {formatDuration(rows.reduce((s, r) => s + r.scheduled, 0))} scheduled
                  {!plan.complete && (
                    <span className="font-semibold text-danger">
                      {" "}
                      · {plan.unmet.length} did not fit
                    </span>
                  )}
                </>
              ) : (
                "Reading the plan..."
              )}
            </p>
          </div>
        </header>

        {error && (
          <div className="mb-6 rounded-card border border-red-200 bg-red-50/70 p-4 text-[13.5px] text-danger shadow-xs">
            {error}
          </div>
        )}

        {plan && rows.length === 0 && !error && (
          <div className="rounded-card border border-black/[0.06] bg-surface p-12 text-center shadow-sm">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-indigo-600">
              <Sparkles size={22} />
            </div>
            <p className="text-[16px] font-semibold text-fg">Nothing scheduled yet</p>
            <p className="mx-auto mt-1.5 max-w-sm text-[13.5px] leading-relaxed text-fg-muted">
              Press <kbd className="tabular rounded-md border border-black/5 bg-sunk px-2 py-0.5 text-[11.5px] font-mono">⌘K</kbd> and describe what you need time for - &quot;write the Q3 doc, 3 hours by Friday&quot;.
            </p>
          </div>
        )}

        <ul className="space-y-3">
          {rows.map(({ intent, blocks, scheduled, short, next, percent }) => (
            <li
              key={intent.id}
              className="group relative overflow-hidden rounded-card border border-black/[0.06] bg-surface p-4.5 shadow-sm transition-all duration-200 ease-spring hover:border-black/15 hover:shadow-md"
            >
              <div className="flex items-start gap-4">
                {/* Left Priority Bar Indicator */}
                <div
                  className="mt-1 h-10 w-1 shrink-0 rounded-full"
                  style={{ background: PRIORITY_TINT[intent.priority as Priority] }}
                  aria-hidden
                />

                <div className="mt-1 shrink-0 text-accent">
                  <Glyph kind={intent.kind} size={18} />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="truncate text-[15px] font-semibold text-fg">{intent.title}</span>
                    <span className="tabular text-[12px] font-medium text-fg-muted">
                      {KIND_LABEL[intent.kind]} · {PRIORITY_NAME[intent.priority as Priority]}
                      {intent.period_days ? ` · every ${intent.period_days}d` : ""}
                    </span>
                  </div>

                  <div className="tabular mt-1.5 flex flex-wrap items-center gap-2 text-[12.5px] text-fg-muted">
                    {next ? (
                      <>
                        <span className="inline-flex items-center gap-1 font-medium text-fg">
                          <Clock size={13} className="text-accent" />
                          {new Date(next.start).toLocaleString([], {
                            weekday: "short",
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </span>
                        <span>·</span>
                        <span>{blocks.length} {blocks.length === 1 ? "block" : "blocks"}</span>
                        <span>·</span>
                        <span>{formatDuration(scheduled)} of {formatDuration(intent.minutes_per_period)}</span>
                      </>
                    ) : (
                      <span className="font-semibold text-danger">Not placed</span>
                    )}
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-3 flex items-center gap-3">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunk">
                      <div
                        className="h-full rounded-full bg-accent transition-[width] duration-300"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                    <span className="tabular text-[11px] font-medium text-fg-muted">{percent}%</span>
                  </div>

                  {short > 0 && (
                    <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-red-50 px-2.5 py-1 text-[12px] font-medium text-danger">
                      <AlertCircle size={13} />
                      {formatDuration(short)} could not be placed - widen its window or lower priority.
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => remove(intent.id)}
                  disabled={busy === intent.id}
                  aria-label={`Remove ${intent.title}`}
                  className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-fg-subtle opacity-0 transition-all duration-150 hover:bg-red-50 hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-40"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </main>
    </Shell>
  );
}
