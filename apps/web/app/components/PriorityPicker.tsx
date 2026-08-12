"use client";

import { PRIORITY_NAME, PRIORITY_TINT, type Priority } from "@/app/lib/api";

/** The priority-pill row shared by every intent-creation form (Habits,
 *  Meetings) - one accent-tint dot per priority, reading the same
 *  `PRIORITY_TINT` every other view (inbox, planner, analytics) uses, so a
 *  priority reads the same way wherever it's picked or shown. */
export function PriorityPicker({
  value,
  onChange,
}: {
  value: Priority;
  onChange: (priority: Priority) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      {([1, 2, 3, 4] as const).map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onChange(p)}
          aria-pressed={value === p}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all duration-150 ${
            value === p ? "bg-surface shadow-sm border border-black/[0.08]" : "text-fg-muted hover:bg-surface/60"
          }`}
        >
          <span className="h-3 w-1 rounded-full" style={{ background: PRIORITY_TINT[p] }} aria-hidden />
          {PRIORITY_NAME[p]}
        </button>
      ))}
    </div>
  );
}
