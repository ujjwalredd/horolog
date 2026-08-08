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

/** Task inbox: every intent, and where the scheduler actually put it.
 *
 *  Deliberately not a plain to-do list. The one question a scheduling product
 *  has to answer that a to-do app cannot is "when is this happening" — so each
 *  row leads with its placement, and anything that did not fit is called out
 *  rather than left looking identical to work that did.
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
        return {
          intent,
          blocks: mine,
          scheduled: mine.reduce((sum, b) => sum + minutesBetween(b.start, b.end), 0),
          short: shortfall.get(intent.id) ?? 0,
          next: mine[0] ?? null,
        };
      })
      .sort((a, b) => {
        if (a.short !== b.short) return b.short - a.short; // unmet first
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
      <main className="mx-auto max-w-[900px] px-6 py-8">
        <header className="mb-7">
          <h1 className="text-[26px] font-semibold tracking-tight-optical">Task inbox</h1>
          <p className="mt-0.5 text-[13px] text-fg-muted">
            {rows.length} {rows.length === 1 ? "intent" : "intents"} ·{" "}
            {formatDuration(rows.reduce((s, r) => s + r.scheduled, 0))} scheduled
            {plan && !plan.complete && (
              <span className="text-danger"> · {plan.unmet.length} did not fit</span>
            )}
          </p>
        </header>

        {error && (
          <p className="mb-5 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-[13px] text-danger">
            {error}
          </p>
        )}

        {rows.length === 0 && !error && (
          <div className="rounded-card border bg-surface px-6 py-14 text-center shadow-sm">
            <p className="text-[15px] font-medium">Nothing scheduled yet</p>
            <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-fg-muted">
              Press <kbd className="tabular rounded bg-sunk px-1.5 py-0.5 text-[11px]">⌘K</kbd> and
              describe what you need time for — “write the design doc, about 3 hours, by Friday”.
            </p>
          </div>
        )}

        <ul className="space-y-2">
          {rows.map(({ intent, blocks, scheduled, short, next }) => (
            <li
              key={intent.id}
              className="group flex items-start gap-3.5 rounded-card border bg-surface px-4 py-3.5 shadow-sm transition-shadow duration-150 hover:shadow-md"
            >
              <span
                className="mt-0.5 h-9 w-[3px] shrink-0 rounded-full"
                style={{ background: PRIORITY_TINT[intent.priority as Priority] }}
                aria-hidden
              />

              <span className="mt-1 shrink-0 text-fg-subtle">
                <Glyph kind={intent.kind} size={16} />
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                  <span className="truncate text-[14.5px] font-medium">{intent.title}</span>
                  <span className="tabular text-[11px] text-fg-muted">
                    {KIND_LABEL[intent.kind]} · {PRIORITY_NAME[intent.priority as Priority]}
                    {intent.period_days ? ` · every ${intent.period_days}d` : ""}
                  </span>
                </div>

                <div className="tabular mt-1 text-[12px] text-fg-muted">
                  {next ? (
                    <>
                      next{" "}
                      <span className="text-fg">
                        {new Date(next.start).toLocaleString([], {
                          weekday: "short",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </span>{" "}
                      · {blocks.length} {blocks.length === 1 ? "block" : "blocks"} ·{" "}
                      {formatDuration(scheduled)} of{" "}
                      {formatDuration(intent.minutes_per_period)}
                    </>
                  ) : (
                    <span className="text-danger">not scheduled</span>
                  )}
                </div>

                {short > 0 && (
                  <div className="mt-1.5 inline-flex items-center gap-1.5 rounded-md bg-danger/8 px-2 py-1 text-[11px] text-danger">
                    {formatDuration(short)} could not be placed — widen its window or drop
                    something else
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => remove(intent.id)}
                disabled={busy === intent.id}
                aria-label={`Remove ${intent.title}`}
                // Hidden until hover on pointer devices, always present for
                // keyboard and touch — a control you cannot reach is not a
                // control.
                className="mt-0.5 h-8 w-8 shrink-0 rounded-md text-fg-subtle opacity-0 transition-all duration-150 hover:bg-sunk hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-40 [@media(hover:none)]:opacity-100"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </main>
    </Shell>
  );
}
