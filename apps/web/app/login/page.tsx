"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Wave } from "@/app/components/Wave";
import { Button } from "@/components/ui/button";

export default function Login() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  function enter() {
    setPending(true);
    router.push("/planner");
  }

  return (
    <main className="relative isolate flex min-h-screen items-center justify-center px-6 py-16 bg-background">
      <div className="pointer-events-none absolute inset-x-0 -top-24 -z-10 h-[560px] opacity-45">
        <Wave />
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-[340px] -z-10 h-64 bg-gradient-to-b from-transparent to-background" />

      <div className="w-full max-w-[400px]">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5 hover:opacity-80 transition-opacity text-primary">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="12" cy="12" r="9.25" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M12 6.75V12l3.4 2.1"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-[17px] font-semibold tracking-tight">Horolog</span>
        </Link>

        <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-lg transition-all duration-300">
          <div className="px-7 pb-6 pt-7 text-center">
            <h1 className="text-[21px] font-semibold tracking-tight text-foreground">
              Welcome back
            </h1>
            <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">
              This instance runs on your machine, so there is nothing to sign in to.
              Your calendar never leaves it.
            </p>
          </div>

          <div className="px-7 pb-7">
            <Button
              type="button"
              onClick={enter}
              disabled={pending}
              className="w-full h-11 text-[14px] group"
            >
              {pending ? "Opening…" : "Continue to planner"}
              {!pending && (
                <span className="transition-transform duration-200 group-hover:translate-x-0.5 ml-2">
                  →
                </span>
              )}
            </Button>

            <div className="my-5 flex items-center gap-3">
              <span className="h-px flex-1 bg-border" />
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Running a team instance?
              </span>
              <span className="h-px flex-1 bg-border" />
            </div>

            <div className="rounded-lg border border-border bg-secondary px-4 py-3">
              <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                Put Horolog behind your existing SSO proxy - oauth2-proxy, Authelia,
                Tailscale, Cloudflare Access. The app trusts the identity your proxy
                asserts rather than rolling its own.
              </p>
            </div>
          </div>

          <div className="border-t border-border bg-secondary/70 px-7 py-3.5 text-center">
            <span className="tabular text-[11px] text-muted-foreground">
              No account · no telemetry · AGPL-3.0
            </span>
          </div>
        </div>

        <p className="mt-6 text-center text-[12.5px] text-muted-foreground">
          <Link href="/" className="underline underline-offset-4 hover:text-foreground">
            Back to overview
          </Link>
        </p>
      </div>
    </main>
  );
}
