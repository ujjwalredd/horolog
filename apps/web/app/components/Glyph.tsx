import type { IntentKind } from "@/app/lib/api";

/** Inline SVG rather than an icon package: five glyphs do not justify a
 *  dependency, and inlining keeps them theme-aware via `currentColor`. */
const PATHS: Record<IntentKind, React.ReactNode> = {
  task: (
    <>
      <rect x="3" y="3" width="14" height="14" rx="3" />
      <path d="M7 10.2l2.1 2.1L13.4 8" />
    </>
  ),
  habit: (
    <>
      <path d="M3.5 8.2A6.6 6.6 0 0 1 15.4 6.4" />
      <path d="M16.5 11.8A6.6 6.6 0 0 1 4.6 13.6" />
      <path d="M15.6 3.2v3.4h-3.4M4.4 16.8v-3.4h3.4" />
    </>
  ),
  focus: (
    <>
      <circle cx="10" cy="10" r="7" />
      <circle cx="10" cy="10" r="2.6" />
    </>
  ),
  buffer: (
    <>
      <path d="M4 6h9a3 3 0 0 1 0 6h-1" />
      <path d="M4 6v6a4 4 0 0 0 4 4h1a4 4 0 0 0 4-4" />
    </>
  ),
  meeting: (
    <>
      <circle cx="7.6" cy="7.4" r="2.8" />
      <path d="M3 16.2a4.8 4.8 0 0 1 9.2 0" />
      <path d="M13.2 5.1a2.8 2.8 0 0 1 0 5.4M14.2 16.2a4.8 4.8 0 0 0-1.4-3.4" />
    </>
  ),
};

export function Glyph({ kind, size = 15 }: { kind: IntentKind; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="shrink-0"
    >
      {PATHS[kind]}
    </svg>
  );
}

export const KIND_LABEL: Record<IntentKind, string> = {
  task: "Task",
  habit: "Habit",
  focus: "Focus",
  buffer: "Buffer",
  meeting: "Meeting",
};
