"use client";

import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/app/components/Shell";
import { api, sync, type Plan } from "@/app/lib/api";
import { Copy, Check, Calendar, Server, Download, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";

type Result = { ok: true; events: number } | { ok: false; message: string } | null;

/** Ultra-Luxury Calendar Connections View for Horolog.
 *  Handles ICS subscriptions, CalDAV sync, and 1-click copy for the plan export URL.
 */
export default function Connect() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [icsUrl, setIcsUrl] = useState("");
  const [dav, setDav] = useState({ url: "", username: "", password: "" });
  const [pending, setPending] = useState<"ics" | "caldav" | null>(null);
  const [feedUrl, setFeedUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState<Result>(null);

  const load = useCallback(async () => {
    try {
      setPlan(await api.plan());
    } catch {
      /* plan error handled elsewhere */
    }
  }, []);

  useEffect(() => {
    void load();
    setFeedUrl(`${window.location.origin}/api/plan.ics`);
  }, [load]);

  async function run(kind: "ics" | "caldav") {
    setPending(kind);
    setResult(null);
    try {
      const out =
        kind === "ics"
          ? await sync.ics(icsUrl.trim())
          : await sync.caldav(dav.url.trim(), dav.username, dav.password);
      setResult({ ok: true, events: out.events });
      await load();
    } catch (caught) {
      setResult({
        ok: false,
        message: caught instanceof Error ? caught.message : "Sync failed.",
      });
    } finally {
      setPending(null);
    }
  }

  function handleCopy() {
    if (!feedUrl) return;
    navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const mirrored = plan?.busy.length ?? 0;
  const bySource = (plan?.busy ?? []).reduce<Record<string, number>>((acc, event) => {
    acc[event.source] = (acc[event.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[800px] px-6 py-8">
        <header className="mb-8">
          <h1 className="text-[28px] font-bold text-fg">Calendars & Sync</h1>
          <p className="mt-1 text-[13.5px] text-fg-muted">
            {mirrored} {mirrored === 1 ? "event" : "events"} mirrored across{" "}
            {Object.keys(bySource).length || 0} active sources.
          </p>
        </header>

        {result && (
          <div
            className={`mb-6 flex items-center gap-2.5 rounded-card border p-4 text-[13.5px] font-medium shadow-xs ${
              result.ok
                ? "border-emerald-200 bg-emerald-50/70 text-emerald-800"
                : "border-red-200 bg-red-50/70 text-danger"
            }`}
          >
            {result.ok ? <CheckCircle2 size={18} className="shrink-0 text-emerald-600" /> : <AlertCircle size={18} className="shrink-0" />}
            <span>
              {result.ok
                ? `Successfully synced ${result.events} events. Your plan has been rebuilt around them.`
                : result.message}
            </span>
          </div>
        )}

        {/* Subscribe to ICS Feed Card */}
        <section className="mb-6 overflow-hidden rounded-card border border-black/[0.08] bg-surface shadow-sm transition-shadow hover:shadow-md">
          <div className="border-b border-black/[0.06] px-6 py-4.5">
            <div className="flex items-center gap-2 text-[16px] font-bold text-fg">
              <Calendar size={18} className="text-accent" />
              <span>Subscribe to a published iCal (.ics) feed</span>
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              Paste your Google Calendar or Outlook secret iCal URL to mirror real meetings instantly.
            </p>
          </div>
          <div className="flex flex-wrap gap-2.5 px-6 py-5">
            <input
              value={icsUrl}
              onChange={(e) => setIcsUrl(e.target.value)}
              placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
              className="h-11 min-w-0 flex-1 rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[14px] font-medium outline-none transition-colors focus:border-accent"
            />
            <button
              type="button"
              onClick={() => run("ics")}
              disabled={!icsUrl.trim() || pending !== null}
              className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-accent px-5 text-[13.5px] font-semibold text-on-accent shadow-sm transition-all duration-150 hover:bg-accent-hover hover:shadow-md disabled:opacity-40"
            >
              <RefreshCw size={15} className={pending === "ics" ? "animate-spin" : ""} />
              {pending === "ics" ? "Syncing..." : "Sync Feed"}
            </button>
          </div>
          <p className="border-t border-black/[0.06] bg-sunk/40 px-6 py-3 text-[12px] text-fg-muted font-medium">
            RRULE events are expanded automatically; TRANSPARENT (free) markers are ignored.
          </p>
        </section>

        {/* CalDAV Card */}
        <section className="mb-6 overflow-hidden rounded-card border border-black/[0.08] bg-surface shadow-sm transition-shadow hover:shadow-md">
          <div className="border-b border-black/[0.06] px-6 py-4.5">
            <div className="flex items-center gap-2 text-[16px] font-bold text-fg">
              <Server size={18} className="text-accent" />
              <span>Connect a CalDAV Server</span>
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              Radicale, Nextcloud, Fastmail, iCloud, Zimbra - full offline air-gapped sync.
            </p>
          </div>
          <div className="grid gap-3 px-6 py-5 sm:grid-cols-3">
            <input
              value={dav.url}
              onChange={(e) => setDav({ ...dav, url: e.target.value })}
              placeholder="https://dav.example.com/"
              className="h-11 rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[14px] font-medium outline-none focus:border-accent sm:col-span-3"
            />
            <input
              value={dav.username}
              onChange={(e) => setDav({ ...dav, username: e.target.value })}
              placeholder="username"
              autoComplete="username"
              className="h-11 rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[14px] font-medium outline-none focus:border-accent"
            />
            <input
              type="password"
              value={dav.password}
              onChange={(e) => setDav({ ...dav, password: e.target.value })}
              placeholder="app password"
              autoComplete="current-password"
              className="h-11 rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[14px] font-medium outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={() => run("caldav")}
              disabled={!dav.url.trim() || pending !== null}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-accent px-5 text-[13.5px] font-semibold text-on-accent shadow-sm transition-all duration-150 hover:bg-accent-hover hover:shadow-md disabled:opacity-40"
            >
              <RefreshCw size={15} className={pending === "caldav" ? "animate-spin" : ""} />
              {pending === "caldav" ? "Connecting..." : "Connect"}
            </button>
          </div>
        </section>

        {/* Subscribable Plan Feed */}
        <section className="overflow-hidden rounded-card border border-black/[0.08] bg-surface shadow-sm transition-shadow hover:shadow-md">
          <div className="border-b border-black/[0.06] px-6 py-4.5">
            <div className="flex items-center gap-2 text-[16px] font-bold text-fg">
              <Download size={18} className="text-accent" />
              <span>Subscribe to Your Horolog Plan</span>
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              Subscribe read-only from Apple Calendar, Google, or Outlook to see your auto-scheduled blocks alongside external events.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 px-6 py-5">
            <code className="tabular min-w-0 flex-1 truncate rounded-xl border border-black/[0.08] bg-bg px-4 py-2.5 text-[13px] font-mono font-medium text-fg-muted">
              {feedUrl || "/api/plan.ics"}
            </code>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex h-11 items-center gap-2 rounded-xl border border-black/[0.08] bg-surface px-4 text-[13.5px] font-semibold text-fg shadow-sm transition-all duration-150 hover:bg-sunk hover:shadow-md"
            >
              {copied ? <Check size={16} className="text-emerald-600" /> : <Copy size={16} className="text-fg-muted" />}
              {copied ? "Copied!" : "Copy Feed Link"}
            </button>
            <a
              href="/api/plan.ics"
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-slate-900 px-4 text-[13.5px] font-semibold text-white shadow-sm transition-all duration-150 hover:bg-slate-800"
            >
              Download .ics
            </a>
          </div>
        </section>
      </main>
    </Shell>
  );
}
