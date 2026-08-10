"use client";

import { useEffect, useState } from "react";
import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import type { Block, Busy, Priority } from "@/app/lib/api";
import { formatDuration, minutesBetween } from "@/app/lib/api";
import { Clock, Calendar, MoveRight } from "lucide-react";

const DAY_START_H = 7;
const DAY_END_H = 21;
const PX_PER_HOUR = 60;
const HEIGHT = (DAY_END_H - DAY_START_H) * PX_PER_HOUR;

const RULE: Record<Priority, string> = {
  1: "#4F46E5",
  2: "#6366F1",
  3: "#818CF8",
  4: "#A5B4FC",
};

const FILL: Record<Priority, string> = {
  1: "rgba(99, 102, 241, 0.12)",
  2: "rgba(99, 102, 241, 0.08)",
  3: "rgba(99, 102, 241, 0.05)",
  4: "rgba(99, 102, 241, 0.03)",
};

const PRIORITY_LABEL: Record<Priority, string> = {
  1: "Critical",
  2: "High",
  3: "Normal",
  4: "Low",
};

function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

function offsetPx(iso: string): number {
  const at = new Date(iso);
  const minutes = at.getHours() * 60 + at.getMinutes() - DAY_START_H * 60;
  return (minutes / 60) * PX_PER_HOUR;
}

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export interface GridProps {
  days: Date[];
  blocks: Block[];
  busy: Busy[];
  selected: string | null;
  onSelect: (key: string | null) => void;
}

/** Ultra-Luxury Week Planner Grid Component.
 *  Includes vibrant current-day pill badges, translucent glass blocks,
 *  dashed borders for relocated tasks, and soft-edge scroll container masks.
 */
export function Grid({ days, blocks, busy, selected, onSelect }: GridProps) {
  const hours = Array.from(
    { length: DAY_END_H - DAY_START_H },
    (_, i) => DAY_START_H + i,
  );
  const todayStr = new Date().toDateString();
  const todayKey = new Date().toISOString().slice(0, 10);

  // Ticks once a minute so the "now" line drifts without a full data reload.
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  const nowTop = offsetPx(now.toISOString());
  const showNowLine = nowTop >= 0 && nowTop <= HEIGHT;

  return (
    <div className="scroll-x scroll-mask-x rounded-card border border-black/[0.08] bg-surface shadow-sm transition-shadow hover:shadow-md">
      <div className="min-w-[900px]">
        {/* Day Header Rail */}
        <div className="sticky top-0 z-20 flex border-b border-black/[0.06] bg-surface/90 backdrop-blur-xl">
          <div className="w-14 shrink-0 border-r border-black/[0.06]" />
          {days.map((day) => {
            const isToday = day.toDateString() === todayStr;
            return (
              <div
                key={day.toISOString()}
                className="flex-1 border-r border-black/[0.06] px-3.5 py-3 last:border-r-0"
              >
                <div className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  {day.toLocaleDateString([], { weekday: "short" })}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span
                    className={`tabular text-[16px] ${
                      isToday
                        ? "inline-flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 font-bold text-white shadow-sm"
                        : "font-semibold text-fg"
                    }`}
                  >
                    {day.getDate()}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Calendar Body */}
        <div className="flex">
          {/* Time Rail */}
          <div className="w-14 shrink-0 border-r border-black/[0.06] bg-sunk/30">
            {hours.map((hour) => (
              <div
                key={hour}
                style={{ height: PX_PER_HOUR }}
                className="relative border-b border-black/[0.04] last:border-b-0"
              >
                <span className="tabular absolute -top-2.5 right-2 rounded bg-surface/90 px-1 py-0.5 text-[10.5px] font-medium text-fg-muted backdrop-blur-sm">
                  {hour % 12 === 0 ? 12 : hour % 12}
                  {hour < 12 ? "a" : "p"}
                </span>
              </div>
            ))}
          </div>

          {/* Grid Columns */}
          {days.map((day) => {
            const key = day.toISOString().slice(0, 10);
            const dayBlocks = blocks.filter((b) => dayKey(b.start) === key);
            const dayBusy = busy.filter((b) => dayKey(b.start) === key);

            return (
              <div
                key={key}
                className="relative flex-1 border-r border-black/[0.06] last:border-r-0"
                style={{ height: HEIGHT }}
              >
                {/* Horizontal Guide Lines */}
                {hours.map((hour) => (
                  <div
                    key={hour}
                    style={{ height: PX_PER_HOUR }}
                    className="border-b border-black/[0.04] last:border-b-0"
                  />
                ))}

                {/* Live "Now" Indicator */}
                {showNowLine && key === todayKey && (
                  <div
                    aria-hidden
                    style={{ top: nowTop }}
                    className="pointer-events-none absolute inset-x-0 z-20 flex items-center transition-[top] duration-500 ease-out motion-reduce:transition-none"
                  >
                    <span className="-ml-1 h-2 w-2 shrink-0 rounded-full bg-danger" />
                    <span className="h-px w-full bg-danger/70" />
                  </div>
                )}

                {/* External Real Meetings (Opaque Sunk Blocks) */}
                {dayBusy.map((event, i) => {
                  const top = offsetPx(event.start);
                  const height = Math.max(
                    18,
                    (minutesBetween(event.start, event.end) / 60) * PX_PER_HOUR,
                  );
                  return (
                    <div
                      key={`${event.start}-${i}`}
                      style={{ top, height }}
                      className="absolute inset-x-1 z-0 overflow-hidden rounded-block border border-black/10 bg-slate-100/90 px-2.5 py-1 backdrop-blur-xs"
                      title={`${event.label || "Busy"} · ${clock(event.start)}`}
                    >
                      <div className="truncate text-[11.5px] font-semibold text-slate-700">
                        {event.label || "Busy"}
                      </div>
                      {height > 32 && (
                        <div className="tabular truncate text-[10px] font-medium text-slate-500">
                          {clock(event.start)}
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Scheduled Auto-Placed Blocks */}
                {dayBlocks.map((block) => {
                  const id = `${block.intent_id}:${block.occurrence}:${block.chunk}`;
                  const minutes = minutesBetween(block.start, block.end);
                  const top = offsetPx(block.start);
                  const height = Math.max(24, (minutes / 60) * PX_PER_HOUR);
                  const moved = block.moved_from !== null && block.moved_from !== block.start;
                  const isSelected = selected === id;

                  const isLinear = block.title.toLowerCase().includes("linear");
                  const isGithub = block.title.toLowerCase().includes("github");
                  const isTodoist = block.title.toLowerCase().includes("todoist");

                  return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => onSelect(isSelected ? null : id)}
                        style={{
                          top,
                          height,
                          background: FILL[block.priority],
                          borderLeft: `3px ${moved ? "dashed" : "solid"} ${RULE[block.priority]}`,
                        }}
                        className={`group absolute inset-x-1.5 z-10 cursor-pointer overflow-hidden rounded-block border border-indigo-200/50 px-2.5 py-1 text-left transition-all duration-200 ease-spring hover:scale-[1.01] hover:shadow-md ${
                          isSelected ? "shadow-md ring-2 ring-secondary0" : "shadow-xs"
                        } ${moved ? "settle" : ""}`}
                      >
                        <div className="flex items-center justify-between gap-1.5">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span style={{ color: RULE[block.priority] }}>
                              <Glyph kind={block.kind} size={13} />
                            </span>
                            <span className="truncate text-[12px] font-semibold text-fg leading-tight">
                              {block.title}
                            </span>
                          </div>
                          {(isLinear || isGithub || isTodoist || block.energy === "high") && (
                            <div className="flex items-center gap-1 shrink-0">
                              {isLinear && (
                                <span className="rounded bg-indigo-500/10 px-1 py-0.2 text-[9px] font-bold text-indigo-600">
                                  Linear
                                </span>
                              )}
                              {isGithub && (
                                <span className="rounded bg-slate-500/10 px-1 py-0.2 text-[9px] font-bold text-slate-700">
                                  GitHub
                                </span>
                              )}
                              {isTodoist && (
                                <span className="rounded bg-red-500/10 px-1 py-0.2 text-[9px] font-bold text-red-600">
                                  Todoist
                                </span>
                              )}
                              {block.energy === "high" && (
                                <span className="rounded bg-amber-500/10 px-1 py-0.2 text-[9px] font-bold text-amber-600" title="High Energy Focus">
                                  ⚡
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        {height > 36 && (
                          <div className="tabular mt-0.5 flex items-center gap-1 truncate text-[10px] font-medium text-fg-muted">
                            <span>{clock(block.start)}</span>
                            <span>·</span>
                            <span>{formatDuration(minutes)}</span>
                          </div>
                        )}
                      </button>
                    );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export { PRIORITY_LABEL, RULE };
