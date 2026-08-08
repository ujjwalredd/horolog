"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Command, ArrowRight, AlertCircle, Loader2 } from "lucide-react";
import { api } from "@/app/lib/api";

const EXAMPLES = [
  "Write the Q3 design doc, 3 hours by Friday",
  "Gym three times a week for an hour, between 10 and 4",
  "Two hours of deep work every morning",
];

/** Apple Spotlight & Stripe-inspired ⌘K Command Bar Popover.
 *  Uses Framer Motion spring physics, glassmorphic backdrop, and natural language capture.
 */
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
      setTimeout(() => input.current?.focus(), 50);
      setError(null);
    } else {
      setText("");
    }
  }, [open]);

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
      setError(caught instanceof Error ? caught.message : "Could not read that request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[16vh]">
          {/* Glass Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-900/20 backdrop-blur-md"
            aria-hidden
          />

          {/* Modal Container */}
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: -12 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0, y: -8 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            className="relative z-10 w-full max-w-xl overflow-hidden rounded-modal border border-black/[0.08] bg-surface shadow-pop"
            role="dialog"
            aria-modal="true"
            aria-label="Describe what you need time for"
          >
            <form onSubmit={submit}>
              <div className="flex items-center gap-3.5 border-b border-black/[0.06] px-4.5 py-1">
                <Sparkles size={18} className="shrink-0 text-accent" />
                <input
                  ref={input}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Escape" && onClose()}
                  placeholder="Describe what you need time for..."
                  disabled={busy}
                  className="h-14 flex-1 bg-transparent text-[15.5px] font-medium outline-none placeholder:text-fg-muted disabled:opacity-60"
                />
                {busy ? (
                  <span className="tabular flex items-center gap-1.5 text-[12px] font-medium text-accent">
                    <Loader2 size={13} className="animate-spin" />
                    Parsing...
                  </span>
                ) : (
                  <kbd className="tabular rounded-md border border-black/5 bg-sunk/80 px-1.5 py-0.5 text-[11px] font-mono text-fg-muted">
                    ESC
                  </kbd>
                )}
              </div>

              {error ? (
                <div className="bg-red-50/60 px-5 py-4 border-b border-red-100">
                  <div className="flex items-center gap-2 text-[13px] font-semibold text-danger">
                    <AlertCircle size={15} />
                    <span>{error}</span>
                  </div>
                  <p className="mt-1 text-[12px] text-fg-muted">
                    Try stating the duration and frequency (e.g. &quot;3 hours by Friday&quot;).
                  </p>
                </div>
              ) : (
                <div className="px-5 py-3.5 bg-surface/50">
                  <p className="mb-2 text-[11px] font-semibold tracking-wider uppercase text-fg-muted">
                    Try natural inputs
                  </p>
                  <div className="flex flex-col gap-1">
                    {EXAMPLES.map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => setText(example)}
                        className="group flex items-center justify-between rounded-lg px-2.5 py-2 text-left text-[13px] text-fg-muted transition-colors duration-150 hover:bg-secondary/70 hover:text-accent"
                      >
                        <span className="truncate">{example}</span>
                        <ArrowRight size={13} className="shrink-0 opacity-0 transition-opacity duration-150 group-hover:opacity-100" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between border-t border-black/[0.06] bg-sunk/60 px-5 py-3">
                <span className="text-[11.5px] text-fg-muted">
                  Auto-scheduled around your real availability.
                </span>
                <button
                  type="submit"
                  disabled={busy || !text.trim()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-on-accent shadow-sm transition-all duration-150 hover:bg-accent-hover hover:shadow-md disabled:opacity-40"
                >
                  Schedule
                  <ArrowRight size={14} />
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
