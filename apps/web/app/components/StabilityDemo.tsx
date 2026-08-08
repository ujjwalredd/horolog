"use client";

import { useRef } from "react";
import { useScrollProgress } from "@/app/components/Reveal";

/** The product's whole argument, as a scroll interaction.
 *
 *  Everyone claims "AI reschedules your calendar". The thing that actually
 *  separates a scheduler you trust from one you fight is what happens to the
 *  blocks that *weren't* affected. So rather than assert it, this scrubs the
 *  real behaviour: a meeting lands on Wednesday, the two blocks it collides
 *  with move, and every other block is pinned to the pixel.
 *
 *  The numbers are a fixed demo fixture, not a live solve — but the behaviour
 *  is the same invariant the engine is tested against
 *  (`test_a_new_meeting_disturbs_only_its_neighbourhood`).
 */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const HOURS = [9, 10, 11, 12, 13, 14, 15, 16];
const ROW = 34;

interface Demo {
  id: string;
  title: string;
  day: number;
  from: number;
  to: number;
  span: number;
  tier: 1 | 2 | 3 | 4;
}

// `from` and `to` are hour offsets. Only the two blocks on Wednesday differ.
const BLOCKS: Demo[] = [
  { id: "a", title: "Deep work", day: 0, from: 9, to: 9, span: 2, tier: 1 },
  { id: "b", title: "Review PRs", day: 0, from: 14, to: 14, span: 1, tier: 3 },
  { id: "c", title: "Deep work", day: 1, from: 10, to: 10, span: 2, tier: 1 },
  { id: "d", title: "Gym", day: 1, from: 15, to: 15, span: 1, tier: 4 },
  { id: "e", title: "Spec draft", day: 2, from: 10, to: 14, span: 2, tier: 2 },
  { id: "f", title: "Gym", day: 2, from: 12, to: 16, span: 1, tier: 4 },
  { id: "g", title: "Deep work", day: 3, from: 9, to: 9, span: 2, tier: 1 },
  { id: "h", title: "1:1 prep", day: 3, from: 13, to: 13, span: 1, tier: 3 },
  { id: "i", title: "Deep work", day: 4, from: 10, to: 10, span: 2, tier: 1 },
  { id: "j", title: "Inbox", day: 4, from: 15, to: 15, span: 1, tier: 4 },
];

const TIER: Record<1 | 2 | 3 | 4, string> = {
  1: "color-mix(in srgb, var(--color-accent) 100%, transparent)",
  2: "color-mix(in srgb, var(--color-accent) 62%, transparent)",
  3: "color-mix(in srgb, var(--color-accent) 38%, transparent)",
  4: "color-mix(in srgb, var(--color-accent) 20%, transparent)",
};

function ease(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function StabilityDemo() {
  const track = useRef<HTMLDivElement>(null);
  const progress = useScrollProgress(track);

  // Three beats: settled week → the meeting appears → displaced work relocates.
  const meetingIn = Math.min(1, Math.max(0, (progress - 0.24) / 0.2));
  const shift = ease(Math.min(1, Math.max(0, (progress - 0.48) / 0.28)));
  const movedCount = shift > 0.5 ? 2 : 0;

  return (
    <div ref={track} className="relative h-[280vh]">
      <div className="sticky top-0 flex min-h-screen items-center py-20">
        <div className="mx-auto w-full max-w-5xl px-6">
          <div className="mb-10 max-w-2xl">
            <p className="mb-3 text-[12px] font-medium uppercase tracking-[0.14em] text-accent">
              The part nobody else gets right
            </p>
            <h2 className="text-[clamp(1.9rem,4vw,3rem)] font-semibold leading-[1.08]">
              A meeting lands. Two blocks move.
              <br />
              <span className="text-fg-muted">Everything else stays exactly where it was.</span>
            </h2>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-fg-muted">
              Most AI calendars re-plan your whole week whenever anything changes, so
              you stop trusting what you see. Horolog treats stability as something to
              optimise for — the schedule you looked at this morning is still the
              schedule at lunch.
            </p>
          </div>

          <div className="overflow-hidden rounded-card border bg-surface shadow-md">
            <div className="flex border-b bg-sunk/60">
              <div className="w-12 shrink-0 border-r" />
              {DAYS.map((day) => (
                <div
                  key={day}
                  className="flex-1 border-r px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-fg-muted last:border-r-0"
                >
                  {day}
                </div>
              ))}
            </div>

            <div className="flex">
              <div className="w-12 shrink-0 border-r">
                {HOURS.map((hour) => (
                  <div key={hour} style={{ height: ROW }} className="relative border-b last:border-b-0">
                    <span className="tabular absolute -top-1.5 right-1.5 bg-surface px-1 text-[10px] text-fg-muted">
                      {hour > 12 ? hour - 12 : hour}
                      {hour < 12 ? "a" : "p"}
                    </span>
                  </div>
                ))}
              </div>

              {DAYS.map((day, dayIndex) => (
                <div
                  key={day}
                  className="relative flex-1 border-r last:border-r-0"
                  style={{ height: HOURS.length * ROW }}
                >
                  {HOURS.map((hour) => (
                    <div key={hour} style={{ height: ROW }} className="border-b last:border-b-0" />
                  ))}

                  {dayIndex === 2 && (
                    <div
                      className="absolute inset-x-1 z-20 overflow-hidden rounded-block border border-line-strong bg-sunk px-2"
                      style={{
                        top: (10 - HOURS[0]!) * ROW,
                        height: ROW * 3,
                        opacity: meetingIn,
                        transform: `scale(${0.94 + meetingIn * 0.06})`,
                        transformOrigin: "center",
                      }}
                    >
                      <div className="pt-1 text-[10px] font-medium leading-tight text-fg-muted">
                        Offsite
                      </div>
                      <div className="tabular text-[9px] text-fg-muted">10:00–13:00</div>
                    </div>
                  )}

                  {BLOCKS.filter((b) => b.day === dayIndex).map((block) => {
                    const moves = block.from !== block.to;
                    const hour = moves ? block.from + (block.to - block.from) * shift : block.from;
                    const nudged = moves && shift > 0.02;
                    return (
                      <div
                        key={block.id}
                        className="absolute inset-x-1 z-10 overflow-hidden rounded-block border px-2"
                        style={{
                          top: (hour - HOURS[0]!) * ROW,
                          height: ROW * block.span,
                          background: `color-mix(in srgb, var(--color-accent) ${
                            10 - block.tier
                          }%, var(--color-surface))`,
                          borderLeft: `2px ${nudged ? "dashed" : "solid"} ${TIER[block.tier]}`,
                          boxShadow: nudged
                            ? `0 0 0 ${3 * (1 - Math.abs(shift - 0.5) * 2)}px color-mix(in srgb, var(--color-accent) 18%, transparent)`
                            : "var(--shadow-sm)",
                        }}
                      >
                        <div className="truncate pt-1 text-[10px] font-medium leading-tight">
                          {block.title}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between border-t bg-sunk/60 px-4 py-2.5">
              <span className="tabular text-[11px] text-fg-muted">
                {movedCount} of {BLOCKS.length} blocks moved
              </span>
              <span className="tabular text-[11px] text-fg-muted">
                re-planned in 3ms
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
