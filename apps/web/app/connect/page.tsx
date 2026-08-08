"use client";

import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/app/components/Shell";
import { api, sync, type Plan } from "@/app/lib/api";

type Result = { ok: true; events: number } | { ok: false; message: string } | null;

/** Calendar connections.
 *
 *  ICS first, CalDAV second — deliberately. A published iCal address works
 *  against Google and Outlook today with no OAuth app, no verified domain and
 *  no publicly reachable callback, which is the difference between "clone the
 *  repo and it works" and "register an app first".
 */
export default function Connect() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [icsUrl, setIcsUrl] = useState("");
  const [dav, setDav] = useState({ url: "", username: "", password: "" });
  const [pending, setPending] = useState<"ics" | "caldav" | null>(null);
  const [feedUrl, setFeedUrl] = useState("");
  const [result, setResult] = useState<Result>(null);

  const load = useCallback(async () => {
    try {
      setPlan(await api.plan());
    } catch {
      /* the banner on the planner already reports an unreachable API */
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

  const mirrored = plan?.busy.length ?? 0;
  const bySource = (plan?.busy ?? []).reduce<Record<string, number>>((acc, event) => {
    acc[event.source] = (acc[event.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Shell onPlanChange={load}>
      <main className="mx-auto max-w-[760px] px-6 py-8">
        <header className="mb-7">
          <h1 className="text-[26px] font-semibold tracking-tight-optical">Calendars</h1>
          <p className="mt-0.5 text-[13px] text-fg-muted">
            {mirrored} {mirrored === 1 ? "event" : "events"} mirrored
            {Object.keys(bySource).length > 0 && (
              <>
                {" · "}
                {Object.entries(bySource)
                  .map(([source, count]) => `${count} from ${source}`)
                  .join(", ")}
              </>
            )}
          </p>
        </header>

        {result && (
          <p
            className={`mb-5 rounded-card border px-4 py-3 text-[13px] ${
              result.ok
                ? "border-ok/30 bg-ok/5 text-ok"
                : "border-danger/30 bg-danger/5 text-danger"
            }`}
          >
            {result.ok
              ? `Mirrored ${result.events} events. Your plan has been rebuilt around them.`
              : result.message}
          </p>
        )}

        <section className="mb-5 overflow-hidden rounded-card border bg-surface shadow-sm">
          <div className="border-b px-5 py-4">
            <h2 className="text-[15px] font-medium">Subscribe to a calendar feed</h2>
            <p className="mt-1 text-[12.5px] leading-relaxed text-fg-muted">
              Any published <code className="tabular text-[11.5px]">.ics</code> address. In Google
              Calendar: Settings → your calendar → <em>Secret address in iCal format</em>. In
              Outlook: Settings → Calendar → Shared calendars → <em>Publish</em>.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 px-5 py-4">
            <input
              value={icsUrl}
              onChange={(e) => setIcsUrl(e.target.value)}
              placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
              className="h-10 min-w-0 flex-1 rounded-md border bg-bg px-3 text-[13.5px] outline-none transition-colors focus:border-accent"
            />
            <button
              type="button"
              onClick={() => run("ics")}
              disabled={!icsUrl.trim() || pending !== null}
              className="h-10 shrink-0 rounded-md bg-accent px-4 text-[13px] font-medium text-on-accent transition-colors duration-150 hover:bg-accent-hover disabled:opacity-40"
            >
              {pending === "ics" ? "Syncing…" : "Sync"}
            </button>
          </div>
          <p className="border-t bg-sunk px-5 py-2.5 text-[11.5px] text-fg-muted">
            Recurring events are expanded, and anything marked free — holidays, other tools&rsquo;
            placeholder blocks — is ignored.
          </p>
        </section>

        <section className="mb-5 overflow-hidden rounded-card border bg-surface shadow-sm">
          <div className="border-b px-5 py-4">
            <h2 className="text-[15px] font-medium">Connect a CalDAV server</h2>
            <p className="mt-1 text-[12.5px] leading-relaxed text-fg-muted">
              Radicale, Nextcloud, Fastmail, iCloud, Zimbra. The only route that works with no
              outbound internet at all.
            </p>
          </div>
          <div className="grid gap-2 px-5 py-4 sm:grid-cols-3">
            <input
              value={dav.url}
              onChange={(e) => setDav({ ...dav, url: e.target.value })}
              placeholder="https://dav.example.com/"
              className="h-10 rounded-md border bg-bg px-3 text-[13.5px] outline-none focus:border-accent sm:col-span-3"
            />
            <input
              value={dav.username}
              onChange={(e) => setDav({ ...dav, username: e.target.value })}
              placeholder="username"
              autoComplete="username"
              className="h-10 rounded-md border bg-bg px-3 text-[13.5px] outline-none focus:border-accent"
            />
            <input
              type="password"
              value={dav.password}
              onChange={(e) => setDav({ ...dav, password: e.target.value })}
              placeholder="app password"
              autoComplete="current-password"
              className="h-10 rounded-md border bg-bg px-3 text-[13.5px] outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={() => run("caldav")}
              disabled={!dav.url.trim() || pending !== null}
              className="h-10 rounded-md bg-accent px-4 text-[13px] font-medium text-on-accent transition-colors duration-150 hover:bg-accent-hover disabled:opacity-40"
            >
              {pending === "caldav" ? "Connecting…" : "Connect"}
            </button>
          </div>
        </section>

        <section className="overflow-hidden rounded-card border bg-surface shadow-sm">
          <div className="border-b px-5 py-4">
            <h2 className="text-[15px] font-medium">Subscribe to your plan</h2>
            <p className="mt-1 text-[12.5px] leading-relaxed text-fg-muted">
              Point any calendar app at this feed to see scheduled blocks alongside your real
              events. Read-only, so it can never modify the calendar it came from.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 px-5 py-4">
            {/* Resolved after mount rather than via a `typeof window` branch:
                that renders differently on the server and the client, which
                trips React's hydration check and throws away this subtree. */}
            <code className="tabular min-w-0 flex-1 truncate rounded-md border bg-bg px-3 py-2.5 text-[12.5px] text-fg-muted">
              {feedUrl || "/api/plan.ics"}
            </code>
            <a
              href="/api/plan.ics"
              className="h-10 shrink-0 rounded-md border bg-surface px-4 text-[13px] font-medium leading-10 shadow-sm transition-colors duration-150 hover:bg-sunk"
            >
              Download
            </a>
          </div>
        </section>
      </main>
    </Shell>
  );
}
