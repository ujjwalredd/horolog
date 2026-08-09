"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, X, Sparkles } from "lucide-react";
import { api } from "@/app/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const TEMPLATES = [
  { label: "💻 Deep Work 2h daily", value: "deep work 2 hours every morning" },
  { label: "🏋️ Gym 1.5h Mon Wed Fri", value: "gym 1.5 hours on Monday, Wednesday, Friday" },
  { label: "📚 Study Math 3h by Friday", value: "study math 3 hours by Friday" },
  { label: "🥪 Lunch 1h at 12pm", value: "lunch break 1 hour at 12pm daily" },
  { label: "🚶 Walk 30m every evening", value: "evening walk 30 minutes every evening" },
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
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("default");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setError(null);
      setInput("");
    }
  }, [open]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleProviderChange = (value: string) => {
    setProvider(value);
  };

  const handleSubmit = async () => {
    if (!input.trim() || busy) return;
    setBusy(true);
    setError(null);

    let model = "default";
    if (provider === "openai") {
      model = "gpt-4o";
    } else if (provider === "anthropic") {
      model = "claude-3-5-sonnet-latest";
    }

    const customKey = (provider === "openai" || provider === "anthropic") ? apiKey.trim() : undefined;

    try {
      await api.capture(input.trim(), provider, model, customKey);
      onCaptured();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not read that request.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          {/* Solid Backdrop (No blur) */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-900/30"
            aria-hidden
          />

          {/* Modal Container - Unified clean minimalist luxury panel */}
          <motion.div
            initial={{ scale: 0.96, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0, y: 8 }}
            transition={{ type: "spring", stiffness: 400, damping: 28 }}
            className="relative z-10 w-full max-w-xl overflow-hidden rounded-card border border-black/[0.08] bg-surface shadow-lg flex flex-col text-fg"
            role="dialog"
            aria-modal="true"
            aria-label="Describe what you need time for"
          >
            {/* Modal Header */}
            <div className="flex justify-between items-center px-5 py-3.5 border-b border-black/[0.05]">
              <span className="text-[13.5px] font-bold text-fg">Add Time via AI Prompt</span>
              
              <div className="flex items-center gap-3">
                {/* Model Selector Dropdown - Solid White bg override to avoid transparency issues */}
                <Select onValueChange={handleProviderChange} value={provider}>
                  <SelectTrigger className="w-40 font-medium h-7 text-[11px] bg-white border border-black/[0.06]" variant="ghost">
                    <SelectValue placeholder="Select LLM Engine" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border border-black/[0.08] shadow-md z-[99] text-xs">
                    <SelectItem value="default" className="hover:bg-slate-100 cursor-pointer">Default LLM</SelectItem>
                    <SelectItem value="openai" className="hover:bg-slate-100 cursor-pointer">OpenAI (GPT-4o)</SelectItem>
                    <SelectItem value="anthropic" className="hover:bg-slate-100 cursor-pointer">Anthropic (Claude 3.5)</SelectItem>
                  </SelectContent>
                </Select>

                <button
                  onClick={onClose}
                  className="text-fg-subtle hover:text-fg cursor-pointer transition-colors p-1"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* API Key configuration input */}
            {(provider === "openai" || provider === "anthropic") && (
              <div className="px-5 pt-3">
                <Input
                  type="password"
                  placeholder={`Enter custom ${provider === "openai" ? "OpenAI" : "Anthropic"} API Key...`}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="h-8.5 text-xs bg-white"
                />
              </div>
            )}

            {/* Error banner */}
            {error && (
              <div className="mx-5 mt-3 p-3 border border-red-200/60 bg-red-50/70 rounded-xl flex items-start gap-2">
                <AlertCircle size={14} className="text-danger shrink-0 mt-0.5" />
                <div>
                  <span className="text-[12.5px] font-semibold text-danger">{error}</span>
                  <p className="text-[11.5px] text-fg-muted mt-0.5">
                    State the duration & frequency (e.g. "gym 1 hour three times a week" or "study 2 hours by Friday").
                  </p>
                </div>
              </div>
            )}

            {/* Input prompt text area */}
            <div className="px-5 pt-4 pb-2">
              <Textarea
                placeholder="e.g., 'deep work 2 hours every morning' or 'sync meetings, 1 hour by Friday'..."
                value={input}
                onChange={handleInputChange}
                disabled={busy}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleSubmit();
                  }
                }}
                className="w-full border-none ring-0 outline-none shadow-none focus:border-none focus:ring-0 focus:outline-none focus:shadow-none hover:border-none hover:ring-0 hover:outline-none hover:shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 resize-none bg-transparent min-h-[90px] text-[14px]"
              />
            </div>

            {/* Sample Query Templates Pills */}
            <div className="px-5 pb-5 flex flex-col gap-2.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Quick Templates</span>
              <div className="flex flex-wrap gap-2">
                {TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.label}
                    type="button"
                    onClick={() => setInput(tmpl.value)}
                    className="px-2.5 py-1.5 rounded-lg border border-black/[0.05] bg-stone-100 hover:bg-stone-200 hover:border-black/[0.1] text-[11px] font-medium text-stone-600 transition-all active:scale-[0.98] cursor-pointer"
                  >
                    {tmpl.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Footer actions row */}
            <div className="flex justify-between items-center px-5 py-3.5 border-t border-black/[0.05] bg-stone-50/50">
              <div className="flex items-center gap-1 text-[11px] font-medium text-slate-400">
                <Sparkles size={12} className="text-slate-300" />
                <span>Horolog AI engine processes focus blocks automatically.</span>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  onClick={onClose}
                  className="h-8.5 px-3.5 rounded-lg text-xs font-bold text-fg-muted cursor-pointer hover:bg-stone-100"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSubmit}
                  loading={busy}
                  disabled={busy || !input.trim()}
                  className="h-8.5 px-4.5 rounded-lg bg-accent text-on-accent text-xs font-bold cursor-pointer hover:bg-accent-hover transition-colors"
                >
                  {busy ? "Parsing..." : "Schedule"}
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
