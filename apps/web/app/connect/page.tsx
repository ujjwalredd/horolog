"use client";

import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/app/components/Shell";
import { api, calendarPush, connections, sync, type Plan, type Provider } from "@/app/lib/api";
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  Copy,
  Download,
  Server,
  Unplug,
  UploadCloud,
} from "lucide-react";

type Result =
  | { ok: true; count: number; label: string; kind?: "sync" | "push" }
  | { ok: false; message: string }
  | null;

const CALENDAR_PROVIDERS: { id: Provider; label: string; icon: React.ReactNode }[] = [
  {
    id: "google",
    label: "Google Calendar",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" className="shrink-0">
        <path d="M21.35,11.1H12v2.7h5.38c-0.24,1.28 -0.96,2.37 -2.04,3.1v2.58h3.3c1.93,-1.78 3.04,-4.4 3.04,-7.48c0,-0.61 -0.05,-1.2 -0.15,-1.78Z" fill="#4285F4" />
        <path d="M12,20.6c2.43,0 4.47,-0.8 5.96,-2.18l-3.3,-2.58c-0.91,0.61 -2.08,0.98 -3.3,0.98c-2.35,0 -4.34,-1.58 -5.05,-3.72H2.9v2.66c1.48,2.94 4.51,4.84 8.02,4.84Z" fill="#34A853" />
        <path d="M6.95,13.1c-0.18,-0.54 -0.28,-1.11 -0.28,-1.7c0,-0.59 0.1,-1.16 0.28,-1.7V7.04H2.9C2.29,8.27 1.95,9.65 1.95,11.1c0,1.45 0.34,2.83 0.95,4.06l3.1,-2.42c-0.08,-0.22 -0.08,-0.42 -0.08,-0.64Z" fill="#FBBC05" />
        <path d="M12,4.18c1.32,0 2.5,0.45 3.44,1.35l2.58,-2.58C16.46,1.46 14.43,0.6 12,0.6C8.49,0.6 5.46,2.5 3.98,5.44l3.1,2.42c0.71,-2.14 2.7,-3.72 5.05,-3.72Z" fill="#EA4335" />
      </svg>
    ),
  },
  {
    id: "outlook",
    label: "Outlook / Microsoft 365",
    icon: (
      <svg viewBox="0 0 23 23" width="18" height="18" className="shrink-0">
        <rect x="0" y="0" width="11" height="11" fill="#F25022" />
        <rect x="12" y="0" width="11" height="11" fill="#7FBA00" />
        <rect x="0" y="12" width="11" height="11" fill="#00A1F1" />
        <rect x="12" y="12" width="11" height="11" fill="#FFB900" />
      </svg>
    ),
  },
];

const TRACKER_PROVIDERS: {
  id: Provider;
  label: string;
  className: string;
  /** No OAuth app exists for this provider (see integrations/<id>.py's
   *  docstring for why) — render the paste-a-credential input only, never
   *  the OAuth "Connect" button, which would point at a route that doesn't
   *  exist. */
  keyOnly?: boolean;
  placeholder?: string;
}[] = [
  { id: "linear", label: "Linear", className: "bg-[#5e6ad2] hover:bg-[#4b55a8] text-white" },
  {
    id: "todoist",
    label: "Todoist",
    className: "border border-red-200 bg-red-50/40 hover:bg-red-50 text-[#e44332]",
  },
  { id: "github", label: "GitHub", className: "bg-slate-900 hover:bg-slate-800 text-white" },
  {
    id: "notion",
    label: "Notion",
    className: "bg-black hover:bg-neutral-800 text-white",
    keyOnly: true,
    placeholder: "database_id:integration_token",
  },
  {
    id: "clickup",
    label: "ClickUp",
    className: "bg-[#7b68ee] hover:bg-[#6a58d6] text-white",
    keyOnly: true,
    placeholder: "team_id:api_token",
  },
  {
    id: "jira",
    label: "Jira",
    className: "bg-[#0052cc] hover:bg-[#0047b3] text-white",
    keyOnly: true,
    placeholder: "site:email:api_token",
  },
];

export default function Connect() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [icsUrl, setIcsUrl] = useState("");
  const [dav, setDav] = useState({ url: "", username: "", password: "" });
  const [trackerKeys, setTrackerKeys] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [feedUrl, setFeedUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState<Result>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    // Two independent calls, so one failing doesn't have to take down a page
    // that's still partly usable — but a failure has to be visible somewhere,
    // or the API being down looks identical to a healthy fresh install with
    // nothing connected yet.
    let failure: string | null = null;
    try {
      setPlan(await api.plan());
    } catch (caught) {
      failure = caught instanceof Error ? caught.message : "Could not reach the scheduler.";
    }
    try {
      setConnected(await connections.list());
    } catch (caught) {
      failure ??= caught instanceof Error ? caught.message : "Could not reach the scheduler.";
    }
    setLoadError(failure);
  }, []);

  useEffect(() => {
    void load();
    setFeedUrl(`${window.location.origin}/api/plan.ics`);

    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    const provider = params.get("provider");
    if (status) {
      window.history.replaceState({}, document.title, window.location.pathname);
      if (status === "success" && provider) {
        void runSync(provider as Provider);
      } else if (status === "credentials_missing" && provider) {
        setResult({
          ok: false,
          message: `${provider} has no OAuth app configured on this server. Add HOROLOG_${provider.toUpperCase()}_CLIENT_ID / _SECRET to .env, or use a pasted key below if this provider supports one.`,
        });
      } else if (status === "error") {
        setResult({ ok: false, message: params.get("error") || "Authentication failed." });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  async function runSync(provider: Provider, credential?: string) {
    setPending(provider);
    setResult(null);
    try {
      let count = 0;
      let label = "events";
      if (provider === "google") {
        count = (await sync.google()).events;
      } else if (provider === "outlook") {
        count = (await sync.outlook()).events;
      } else if (provider === "linear") {
        count = (await sync.linear(credential)).issues;
        label = "issues";
      } else if (provider === "todoist") {
        count = (await sync.todoist(credential)).tasks;
        label = "tasks";
      } else if (provider === "github") {
        count = (await sync.github(credential)).issues;
        label = "issues";
      } else if (provider === "notion") {
        count = (await sync.notion(credential ?? "")).tasks;
        label = "tasks";
      } else if (provider === "clickup") {
        count = (await sync.clickup(credential ?? "")).tasks;
        label = "tasks";
      } else if (provider === "jira") {
        count = (await sync.jira(credential ?? "")).issues;
        label = "issues";
      }
      setResult({ ok: true, count, label });
      await load();
    } catch (caught) {
      setResult({ ok: false, message: caught instanceof Error ? caught.message : "Sync failed." });
    } finally {
      setPending(null);
    }
  }

  async function pushCalendar(provider: "google" | "outlook") {
    setPending(`push-${provider}`);
    setResult(null);
    try {
      const out = await calendarPush.push(provider);
      setResult({
        ok: true,
        count: out.created + out.moved + out.removed,
        label: `${out.created} created, ${out.moved} moved, ${out.removed} removed`,
        kind: "push",
      });
    } catch (caught) {
      setResult({ ok: false, message: caught instanceof Error ? caught.message : "Push failed." });
    } finally {
      setPending(null);
    }
  }

  async function disconnect(provider: Provider) {
    setPending(provider);
    try {
      await connections.disconnect(provider);
      await load();
    } finally {
      setPending(null);
    }
  }

  async function runIcs() {
    setPending("ics");
    setResult(null);
    try {
      const out = await sync.ics(icsUrl.trim());
      setResult({ ok: true, count: out.events, label: "events" });
      await load();
    } catch (caught) {
      setResult({ ok: false, message: caught instanceof Error ? caught.message : "Sync failed." });
    } finally {
      setPending(null);
    }
  }

  async function runCaldav() {
    setPending("caldav");
    setResult(null);
    try {
      const out = await sync.caldav(dav.url.trim(), dav.username, dav.password);
      setResult({ ok: true, count: out.events, label: "events" });
      await load();
    } catch (caught) {
      setResult({ ok: false, message: caught instanceof Error ? caught.message : "Sync failed." });
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
      <main className="mx-auto max-w-[800px] space-y-6 px-6 py-8">
        <header className="mb-4">
          <h1 className="text-[28px] font-bold text-fg">Calendars & Sync</h1>
          <p className="mt-1 text-[13.5px] font-medium text-fg-muted">
            {mirrored} {mirrored === 1 ? "event" : "events"} mirrored across{" "}
            {Object.keys(bySource).length || 0} active sources.
          </p>
        </header>

        {loadError && (
          <div className="flex items-center gap-2.5 rounded-card border border-red-200 bg-red-50 p-4 text-[13.5px] font-medium text-danger shadow-sm">
            <AlertCircle size={18} className="shrink-0" />
            <span>{loadError} — sync status below may be stale.</span>
          </div>
        )}

        {result && (
          <div
            className={`flex items-center gap-2.5 rounded-card border p-4 text-[13.5px] font-medium shadow-sm ${
              result.ok
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-danger"
            }`}
          >
            {result.ok ? (
              <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
            ) : (
              <AlertCircle size={18} className="shrink-0" />
            )}
            <span>
              {result.ok
                ? result.kind === "push"
                  ? `Pushed to the calendar: ${result.label}.`
                  : `Synced ${result.count} ${result.label}. Your plan has been rebuilt around them.`
                : result.message}
            </span>
          </div>
        )}

        {/* Calendars — OAuth, or paste an ICS/CalDAV address directly */}
        <section className="space-y-5 overflow-hidden rounded-card border border-black/[0.08] bg-surface p-6 shadow-sm">
          <div>
            <h2 className="text-[15px] font-bold text-fg">Connect a calendar</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              OAuth needs your own app credentials — self-hosting means there is no shared client
              to hand out (see .env.example). The feed and server options below need none.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            {CALENDAR_PROVIDERS.map((p) => {
              const isConnected = connected[p.id];
              return (
                <div key={p.id} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => (isConnected ? runSync(p.id) : (window.location.href = `/api/auth/${p.id}`))}
                    disabled={pending !== null}
                    className="flex h-11 flex-1 items-center justify-center gap-3 rounded-xl border border-black/[0.08] bg-white px-4 text-[13.5px] font-semibold text-stone-700 shadow-sm transition-all hover:bg-stone-50 disabled:opacity-50"
                  >
                    {p.icon}
                    <span>
                      {pending === p.id
                        ? "Working…"
                        : isConnected
                          ? `Re-sync ${p.label}`
                          : `Connect ${p.label}`}
                    </span>
                    {isConnected && <CheckCircle2 size={15} className="text-emerald-600" />}
                  </button>
                  {isConnected && (
                    <button
                      type="button"
                      onClick={() => pushCalendar(p.id as "google" | "outlook")}
                      disabled={pending !== null}
                      aria-label={`Push the plan to ${p.label}`}
                      title={`Push scheduled blocks onto a dedicated "Horolog" calendar on ${p.label} — needs HOROLOG_CALENDAR_WRITEBACK_ENABLED=true`}
                      className="flex h-11 w-11 items-center justify-center rounded-xl border border-black/[0.08] bg-white text-fg-muted transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
                    >
                      {pending === `push-${p.id}` ? (
                        <span className="tabular text-[10px] font-semibold">…</span>
                      ) : (
                        <UploadCloud size={15} />
                      )}
                    </button>
                  )}
                  {isConnected && (
                    <button
                      type="button"
                      onClick={() => disconnect(p.id)}
                      disabled={pending !== null}
                      aria-label={`Disconnect ${p.label}`}
                      title={`Disconnect ${p.label}`}
                      className="flex h-11 w-11 items-center justify-center rounded-xl border border-black/[0.08] bg-white text-fg-muted transition-colors hover:border-red-200 hover:text-danger disabled:opacity-50"
                    >
                      <Unplug size={15} />
                    </button>
                  )}
                </div>
              );
            })}
            <p className="text-[12px] leading-relaxed text-fg-subtle">
              <UploadCloud size={12} className="mb-0.5 mr-1 inline" />
              Push writes scheduled blocks onto a dedicated &quot;Horolog&quot; calendar as real
              events — never your primary calendar. Off by default; enable with{" "}
              <code className="rounded bg-sunk px-1 py-0.5 font-mono">
                HOROLOG_CALENDAR_WRITEBACK_ENABLED=true
              </code>{" "}
              and reconnect the account above once to grant write access.
            </p>
          </div>

          <div className="border-t border-black/[0.06] pt-5">
            <div className="mb-2 flex items-center gap-2 text-[13.5px] font-semibold text-fg">
              <Calendar size={15} className="text-accent" />
              Subscribe to a published iCal (.ics) feed
            </div>
            <div className="flex flex-wrap gap-2.5">
              <input
                value={icsUrl}
                onChange={(e) => setIcsUrl(e.target.value)}
                placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
                className="h-11 min-w-0 flex-1 rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[14px] font-medium outline-none focus:border-accent"
              />
              <button
                type="button"
                onClick={runIcs}
                disabled={!icsUrl.trim() || pending !== null}
                className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-accent px-5 text-[13.5px] font-semibold text-on-accent shadow-sm transition-all hover:bg-accent-hover disabled:opacity-40"
              >
                {pending === "ics" ? "Syncing…" : "Sync Feed"}
              </button>
            </div>
          </div>

          <div className="border-t border-black/[0.06] pt-5">
            <div className="mb-2 flex items-center gap-2 text-[13.5px] font-semibold text-fg">
              <Server size={15} className="text-accent" />
              Connect a CalDAV server
            </div>
            <div className="grid gap-2.5 sm:grid-cols-3">
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
                onClick={runCaldav}
                disabled={!dav.url.trim() || pending !== null}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-accent px-5 text-[13.5px] font-semibold text-on-accent shadow-sm transition-all hover:bg-accent-hover disabled:opacity-40"
              >
                {pending === "caldav" ? "Connecting…" : "Connect"}
              </button>
            </div>
          </div>
        </section>

        {/* Trackers — OAuth, or paste a personal key */}
        <section className="space-y-4 overflow-hidden rounded-card border border-black/[0.08] bg-surface p-6 shadow-sm">
          <div>
            <h2 className="text-[15px] font-bold text-fg">Connect a tracker</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              Started issues and open tasks are scheduled as tasks, fluidly, around everything
              else. A personal API key needs no OAuth app.
            </p>
          </div>
          <div className="space-y-3">
            {TRACKER_PROVIDERS.map((p) => {
              const isConnected = connected[p.id];
              return (
                <div key={p.id} className="flex flex-wrap items-center gap-2">
                  {!p.keyOnly && (
                    <button
                      type="button"
                      onClick={() => (isConnected ? runSync(p.id) : (window.location.href = `/api/auth/${p.id}`))}
                      disabled={pending !== null}
                      className={`flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-[13.5px] font-semibold shadow-sm transition-all disabled:opacity-50 ${p.className}`}
                    >
                      <span>
                        {pending === p.id
                          ? "Working…"
                          : isConnected
                            ? `Re-sync ${p.label}`
                            : `Connect ${p.label}`}
                      </span>
                      {isConnected && <CheckCircle2 size={15} />}
                    </button>
                  )}
                  {isConnected && (
                    <button
                      type="button"
                      onClick={() => disconnect(p.id)}
                      disabled={pending !== null}
                      aria-label={`Disconnect ${p.label}`}
                      title={`Disconnect ${p.label}`}
                      className="flex h-11 w-11 items-center justify-center rounded-xl border border-black/[0.08] bg-white text-fg-muted transition-colors hover:border-red-200 hover:text-danger disabled:opacity-50"
                    >
                      <Unplug size={15} />
                    </button>
                  )}
                  {!p.keyOnly && <span className="text-fg-subtle">or</span>}
                  {p.keyOnly && (
                    <span className="flex h-11 items-center gap-2 rounded-xl px-4 text-[13.5px] font-semibold text-fg-muted">
                      {p.label}
                    </span>
                  )}
                  <input
                    type="password"
                    value={trackerKeys[p.id] ?? ""}
                    onChange={(e) => setTrackerKeys({ ...trackerKeys, [p.id]: e.target.value })}
                    placeholder={p.placeholder ?? "paste a personal API key"}
                    className="h-11 min-w-0 flex-1 rounded-xl border border-black/[0.08] bg-bg px-3.5 text-[13px] font-medium outline-none focus:border-accent"
                  />
                  <button
                    type="button"
                    onClick={() => runSync(p.id, trackerKeys[p.id])}
                    disabled={!trackerKeys[p.id]?.trim() || pending !== null}
                    className="inline-flex h-11 items-center gap-2 rounded-xl border border-black/[0.08] bg-white px-4 text-[13px] font-semibold text-fg shadow-sm transition-all hover:bg-sunk disabled:opacity-40"
                  >
                    Sync
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        {/* Subscribable Plan Feed */}
        <section className="overflow-hidden rounded-card border border-black/[0.08] bg-surface p-6 shadow-sm">
          <div>
            <h2 className="text-[15px] font-bold text-fg">Subscribe to your Horolog plan</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-muted">
              Read-only from Apple Calendar, Google, or Outlook — see your auto-scheduled blocks
              alongside external events.
            </p>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <code className="tabular min-w-0 flex-1 truncate rounded-xl border border-black/[0.08] bg-bg px-4 py-2.5 text-[12.5px] font-mono font-medium text-fg-muted">
              {feedUrl || "/api/plan.ics"}
            </code>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex h-11 items-center gap-2 rounded-xl border border-black/[0.08] bg-surface px-4 text-[13px] font-semibold text-fg shadow-sm transition-all hover:bg-sunk"
            >
              {copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} className="text-fg-muted" />}
              {copied ? "Copied!" : "Copy Feed Link"}
            </button>
            <a
              href="/api/plan.ics"
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-slate-900 px-4 text-[13px] font-semibold text-white shadow-sm transition-all hover:bg-slate-800"
            >
              <Download size={14} /> Download .ics
            </a>
          </div>
        </section>
      </main>
    </Shell>
  );
}
