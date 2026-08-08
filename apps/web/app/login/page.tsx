"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Wave } from "@/app/components/Wave";

/** Entry to the planner.
 *
 *  This build ships single-user and unauthenticated by design: it runs on your
 *  own machine against your own calendar, and inventing a credential store that
 *  protects nothing would be security theatre. The screen is honest about that
 *  rather than presenting a login box that accepts anything — a fake form is
 *  worse than none, because it implies a boundary that isn't there.
 *
 *  When multi-user lands, this is the seam: the same route gains a real form,
 *  and `/planner` gains a session check.
 */
export default function Login() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  function enter() {
    setPending(true);
    router.push("/planner");
  }

  return (
    <main className="relative isolate flex min-h-screen items-center justify-center px-6 py-16">
      <div className="pointer-events-none absolute inset-x-0 -top-24 -z-10 h-[560px] opacity-45">
        <Wave />
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-[340px] -z-10 h-64 bg-gradient-to-b from-transparent to-bg" />

      <div className="w-full max-w-[400px]">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="12" cy="12" r="9.25" stroke="var(--color-fg)" strokeWidth="1.5" />
            <path
              d="M12 6.75V12l3.4 2.1"
              stroke="var(--color-accent)"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-[17px] font-semibold tracking-tight-optical">Horolog</span>
        </Link>

        <div className="rise overflow-hidden rounded-modal border bg-surface shadow-pop">
          <div className="px-7 pb-6 pt-7 text-center">
            <h1 className="text-[21px] font-semibold tracking-tight-optical">
              Welcome back
            </h1>
            <p className="mt-2 text-[13.5px] leading-relaxed text-fg-muted">
              This instance runs on your machine, so there is nothing to sign in to.
              Your calendar never leaves it.
            </p>
          </div>

          <div className="px-7 pb-7">
            <button
              type="button"
              onClick={enter}
              disabled={pending}
              className="group flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-accent text-[14px] font-medium text-on-accent shadow-sm transition-all duration-200 hover:bg-accent-hover hover:shadow-md disabled:opacity-60"
            >
              {pending ? "Opening…" : "Continue to planner"}
              {!pending && (
                <span className="transition-transform duration-200 group-hover:translate-x-0.5">
                  →
                </span>
              )}
            </button>

            <div className="my-5 flex items-center gap-3">
              <span className="h-px flex-1 bg-line" />
              <span className="text-[11px] uppercase tracking-wide text-fg-muted">
                Running a team instance?
              </span>
              <span className="h-px flex-1 bg-line" />
            </div>

            <div className="rounded-lg border bg-sunk px-4 py-3">
              <p className="text-[12.5px] leading-relaxed text-fg-muted">
                Put Horolog behind your existing SSO proxy — oauth2-proxy, Authelia,
                Tailscale, Cloudflare Access. The app trusts the identity your proxy
                asserts rather than rolling its own.
              </p>
            </div>
          </div>

          <div className="border-t bg-sunk/70 px-7 py-3.5 text-center">
            <span className="tabular text-[11px] text-fg-muted">
              No account · no telemetry · AGPL-3.0
            </span>
          </div>
        </div>

        <p className="mt-6 text-center text-[12.5px] text-fg-muted">
          <Link href="/" className="underline underline-offset-4 hover:text-fg">
            Back to overview
          </Link>
        </p>
      </div>
    </main>
  );
}
