"use client";

import { Glyph, KIND_LABEL } from "@/app/components/Glyph";
import type { Block, Busy, Priority } from "@/app/lib/api";
import { formatDuration, minutesBetween } from "@/app/lib/api";

const DAY_START_H = 7;
const DAY_END_H = 21;
const PX_PER_HOUR = 58;
const HEIGHT = (DAY_END_H - DAY_START_H) * PX_PER_HOUR;

/** Priority is carried by the *saturation of the left rule*, not by the fill.
 *
 *  Encoding it as four solid fills would either wash out the low tiers or force
 *  white text on the high ones, and a calendar has to stay readable at a
 *  glance. Keeping fills pale means block text is always --color-fg at AAA
 *  contrast, while the rule still ranks four levels in one hue. Priority is
 *  also never the *only* signal — the glyph carries kind and the rule style
 *  carries movability. */
const RULE: Record<Priority, string> = {
  1: "color-mix(in srgb, var(--color-accent) 100%, transparent)",
  2: "color-mix(in srgb, var(--color-accent) 62%, transparent)",
  3: "color-mix(in srgb, var(--color-accent) 38%, transparent)",
  4: "color-mix(in srgb, var(--color-accent) 20%, transparent)",
};

const FILL: Record<Priority, string> = {
  1: "color-mix(in srgb, var(--color-accent) 9%, var(--color-surface))",
  2: "color-mix(in srgb, var(--color-accent) 7%, var(--color-surface))",
  3: "color-mix(in srgb, var(--color-accent) 5%, var(--color-surface))",
  4: "color-mix(in srgb, var(--color-accent) 3.5%, var(--color-surface))",
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

export function Grid({ days, blocks, busy, selected, onSelect }: GridProps) {
  const hours = Array.from(
    { length: DAY_END_H - DAY_START_H },
    (_, i) => DAY_START_H + i,
  );
  const today = new Date().toDateString();

  return (
    <div className="scroll-x rounded-card border bg-surface shadow-sm">
      <div className="min-w-[880px]">
        {/* Day header */}
        <div className="sticky top-0 z-20 flex border-b bg-surface/95 backdrop-blur">
          <div className="w-14 shrink-0 border-r" />
          {days.map((day) => {
            const isToday = day.toDateString() === today;
            return (
              <div
                key={day.toISOString()}
                className="flex-1 border-r px-3 py-2.5 last:border-r-0"
              >
                <div className="text-[11px] font-medium uppercase tracking-wide text-fg-muted">
                  {day.toLocaleDateString([], { weekday: "short" })}
                </div>
                <div
                  className={`tabular text-[15px] ${
                    isToday ? "font-semibold text-accent" : "text-fg"
                  }`}
                >
                  {day.getDate()}
                </div>
              </div>
            );
          })}
        </div>

        {/* Body */}
        <div className="flex">
          {/* Hour rail — --color-fg-muted, never --color-fg-subtle: at 12px
              this is text and has to clear 4.5:1. */}
          <div className="w-14 shrink-0 border-r">
            {hours.map((hour) => (
              <div
                key={hour}
                style={{ height: PX_PER_HOUR }}
                className="relative border-b last:border-b-0"
              >
                <span className="tabular absolute -top-2 right-2 bg-surface px-1 text-[11px] text-fg-muted">
                  {hour % 12 === 0 ? 12 : hour % 12}
                  {hour < 12 ? "a" : "p"}
                </span>
              </div>
            ))}
          </div>

          {days.map((day) => {
            const key = day.toISOString().slice(0, 10);
            const dayBlocks = blocks.filter((b) => dayKey(b.start) === key);
            const dayBusy = busy.filter((b) => dayKey(b.start) === key);

            return (
              <div
                key={key}
                className="relative flex-1 border-r last:border-r-0"
                style={{ height: HEIGHT }}
              >
                {hours.map((hour) => (
                  <div
                    key={hour}
                    style={{ height: PX_PER_HOUR }}
                    className="border-b last:border-b-0"
                  />
                ))}

                {/* Real meetings: sunk, no accent. "Not ours" has to be
                    obvious without reading a label. */}
                {dayBusy.map((event, i) => {
                  const top = offsetPx(event.start);
                  const height = Math.max(
                    16,
                    (minutesBetween(event.start, event.end) / 60) * PX_PER_HOUR,
                  );
                  return (
                    <div
                      key={`${event.start}-${i}`}
                      style={{ top, height }}
                      className="absolute inset-x-1 z-0 overflow-hidden rounded-block border border-line-strong bg-sunk px-2 py-1"
                      title={`${event.label || "Busy"} · ${clock(event.start)}`}
                    >
                      <div className="truncate text-[11px] font-medium text-fg-muted">
                        {event.label || "Busy"}
                      </div>
                      <div className="tabular truncate text-[10px] text-fg-muted">
                        {clock(event.start)}
                      </div>
                    </div>
                  );
                })}

                {dayBlocks.map((block) => {
                  const id = `${block.intent_id}:${block.occurrence}:${block.chunk}`;
                  const minutes = minutesBetween(block.start, block.end);
                  const top = offsetPx(block.start);
                  const height = Math.max(22, (minutes / 60) * PX_PER_HOUR);
                  const moved = block.moved_from !== null && block.moved_from !== block.start;
                  const isSelected = selected === id;

                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => onSelect(isSelected ? null : id)}
                      style={{
                        top,
                        height,
                        background: FILL[block.priority],
                        borderLeft: `2px ${moved ? "dashed" : "solid"} ${RULE[block.priority]}`,
                      }}
                      className={`absolute inset-x-1 z-10 cursor-pointer overflow-hidden rounded-block border border-line px-2 py-1 text-left transition-shadow duration-150 hover:shadow-md ${
                        isSelected ? "shadow-md ring-1 ring-accent" : "shadow-sm"
                      } ${moved ? "settle" : ""}`}
                      aria-label={`${block.title}, ${KIND_LABEL[block.kind]}, ${
                        PRIORITY_LABEL[block.priority]
                      } priority, ${clock(block.start)} for ${formatDuration(minutes)}${
                        moved ? ", moved from its previous time" : ""
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span style={{ color: RULE[block.priority] }}>
                          <Glyph kind={block.kind} size={13} />
                        </span>
                        <span className="truncate text-[12px] font-medium leading-tight">
                          {block.title}
                        </span>
                      </div>
                      {height > 38 && (
                        <div className="tabular mt-0.5 truncate text-[10px] text-fg-muted">
                          {clock(block.start)} · {formatDuration(minutes)}
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
