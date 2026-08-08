"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { CommandBar } from "@/app/components/CommandBar";

const NAV = [
  { href: "/planner", label: "Planner", icon: "grid" },
  { href: "/inbox", label: "Task inbox", icon: "inbox" },
  { href: "/habits", label: "Habits", icon: "repeat" },
  { href: "/analytics", label: "Analytics", icon: "chart" },
  { href: "/connect", label: "Calendars", icon: "link" },
] as const;

const ICONS: Record<string, React.ReactNode> = {
  grid: (
    <>
      <rect x="3" y="3" width="6.2" height="14" rx="1.6" />
      <rect x="10.8" y="3" width="6.2" height="8" rx="1.6" />
    </>
  ),
  inbox: (
    <>
      <path d="M3 12.2h3.4l1.1 2h4.9l1.2-2H17" />
      <path d="M4.4 4.6h11.2l1.4 7.6v3.2a1.6 1.6 0 0 1-1.6 1.6H4.6A1.6 1.6 0 0 1 3 15.4v-3.2z" />
    </>
  ),
  repeat: (
    <>
      <path d="M3.5 8.2A6.6 6.6 0 0 1 15.4 6.4" />
      <path d="M16.5 11.8A6.6 6.6 0 0 1 4.6 13.6" />
      <path d="M15.6 3.2v3.4h-3.4M4.4 16.8v-3.4h3.4" />
    </>
  ),
  chart: (
    <>
      <path d="M3.4 16.6h13.2" />
      <path d="M6 16.6V9.4M10 16.6V4.6M14 16.6v-4.8" />
    </>
  ),
  link: (
    <>
      <path d="M8.4 11.6a3.4 3.4 0 0 0 5 .4l2-2a3.4 3.4 0 0 0-4.8-4.8l-1.1 1.1" />
      <path d="M11.6 8.4a3.4 3.4 0 0 0-5-.4l-2 2a3.4 3.4 0 0 0 4.8 4.8l1.1-1.1" />
    </>
  ),
};

/** Chrome for the signed-in app: rail, ⌘K, and the live-plan indicator.
 *
 *  Lives in a layout rather than each page so the SSE connection is opened once
 *  for the whole session — a per-page subscription would tear down and re-open
 *  the stream on every navigation, and miss any change that landed in between.
 */
export function Shell({
  children,
  onPlanChange,
}: {
  children: React.ReactNode;
  onPlanChange?: () => void;
}) {
  const pathname = usePathname();
  const [commandOpen, setCommandOpen] = useState(false);
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const stream = new EventSource("/api/stream");
    stream.addEventListener("plan", () => {
      setPulse(true);
      setTimeout(() => setPulse(false), 1100);
      onPlanChange?.();
    });
    return () => stream.close();
  }, [onPlanChange]);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[210px] shrink-0 flex-col border-r bg-surface/60 px-3 py-4 lg:flex">
        <Link href="/" className="mb-6 flex items-center gap-2.5 px-2">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="12" cy="12" r="9.25" stroke="var(--color-fg)" strokeWidth="1.5" />
            <path
              d="M12 6.75V12l3.4 2.1"
              stroke="var(--color-accent)"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-[14.5px] font-semibold tracking-tight-optical">Horolog</span>
        </Link>

        <nav className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[13.5px] transition-colors duration-150 ${
                  active
                    ? "bg-accent/10 font-medium text-accent"
                    : "text-fg-muted hover:bg-sunk hover:text-fg"
                }`}
              >
                <svg
                  width="17"
                  height="17"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  {ICONS[item.icon]}
                </svg>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={() => setCommandOpen(true)}
          className="mt-4 flex h-9 items-center justify-between rounded-md border bg-surface px-2.5 text-[13px] text-fg-muted shadow-sm transition-colors duration-150 hover:bg-sunk hover:text-fg"
        >
          Add time
          <kbd className="tabular rounded bg-sunk px-1.5 py-0.5 text-[10px]">⌘K</kbd>
        </button>

        <div className="mt-auto flex items-center gap-2 px-2.5 pt-4">
          <span
            className={`h-1.5 w-1.5 rounded-full transition-colors duration-300 ${
              pulse ? "bg-accent" : "bg-ok"
            }`}
            aria-hidden
          />
          <span className="text-[11px] text-fg-muted">
            {pulse ? "re-planning…" : "plan is live"}
          </span>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1 overflow-x-auto border-b bg-surface/60 px-4 py-2 lg:hidden">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`shrink-0 rounded-md px-3 py-1.5 text-[13px] ${
                pathname === item.href ? "bg-accent/10 text-accent" : "text-fg-muted"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
        {children}
      </div>

      <CommandBar
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        onCaptured={() => onPlanChange?.()}
      />
    </div>
  );
}
