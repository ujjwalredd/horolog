"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/app/lib/api";

const EXAMPLES = [
  "Write the Q3 review, about 4 hours, due Friday",
  "Gym three times a week for an hour, between 10 and 4",
  "Two hours of deep work every morning",
];

export function CommandBar({
  open,
  onClose,
  onCaptured,
}: {
  open: boolean;
  onClose: () => void;
  onCaptured: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      input.current?.focus();
      setError(null);
    } else {
      setText("");
    }
  }, [open]);

  if (!open) return null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.capture(value);
      onCaptured();
      onClose();
    } catch (caught) {
      // A 422 means the model could not read the request; a 503 means it is
      // unreachable. Either way the user keeps their text and can rephrase —
      // the input is never cleared on failure.
      setError(caught instanceof Error ? caught.message : "Could not read that.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-fg/10 px-4 pt-[18vh] backdrop-blur-[2px]"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="rise w-full max-w-xl overflow-hidden rounded-modal border bg-surface shadow-pop"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Describe what you need time for"
      >
        <form onSubmit={submit}>
          <div className="flex items-center gap-3 border-b px-4">
            <svg
              width="17"
              height="17"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              className="shrink-0 text-fg-muted"
              aria-hidden
            >
              <circle cx="9" cy="9" r="6" />
              <path d="M13.5 13.5L17 17" />
            </svg>
            <input
              ref={input}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && onClose()}
              placeholder="Describe what you need time for…"
              disabled={busy}
              className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-fg-muted disabled:opacity-60"
            />
            {busy && (
              <span className="tabular text-[11px] text-fg-muted">reading…</span>
            )}
          </div>

          {error ? (
            <div className="px-4 py-3">
              <p className="text-[13px] text-danger">{error}</p>
              <p className="mt-1 text-[12px] text-fg-muted">
                Try naming the duration and how often — that is usually what is missing.
              </p>
            </div>
          ) : (
            <div className="px-4 py-3">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-fg-muted">
                For example
              </p>
              <ul className="space-y-1">
                {EXAMPLES.map((example) => (
                  <li key={example}>
                    <button
                      type="button"
                      onClick={() => setText(example)}
                      className="w-full truncate rounded px-2 py-1.5 text-left text-[13px] text-fg-muted transition-colors duration-150 hover:bg-sunk hover:text-fg"
                    >
                      {example}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center justify-between border-t bg-sunk px-4 py-2.5">
            <span className="text-[11px] text-fg-muted">
              Placed by the scheduler, around what is already on your calendar.
            </span>
            <button
              type="submit"
              disabled={busy || !text.trim()}
              className="rounded-md bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent transition-colors duration-150 hover:bg-accent-hover disabled:opacity-40"
            >
              Schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
