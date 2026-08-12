"use client";

import { use, useEffect, useMemo, useState } from "react";
import { CalendarIcon, Check, Clock, Globe, Loader2 } from "lucide-react";
import { booking, type Booked, type FreeSlot } from "@/app/lib/api";

const LENGTHS = [15, 30, 45, 60] as const;
const DAYS = 7;

/** A public booking link.
 *
 *  Every time shown comes from `/api/availability`, which reports *true* free
 *  time: hours currently holding flexible focus work are still offered, because
 *  accepting one pushes that work elsewhere rather than colliding with it. Only
 *  real commitments close a slot.
 */
export default function BookingPage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = use(params);
  const [minutes, setMinutes] = useState<number>(30);
  const [slots, setSlots] = useState<FreeSlot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<FreeSlot | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmed, setConfirmed] = useState<Booked | null>(null);

  useEffect(() => {
    let live = true;
    setSlots(null);
    setError(null);
    setChosen(null);
    booking
      .availability(minutes, DAYS)
      .then((found) => live && setSlots(found))
      .catch((cause: Error) => live && setError(cause.message));
    return () => {
      live = false;
    };
  }, [minutes]);

  // Grouped in the viewer's own zone — a guest picks a time in the timezone
  // they live in, and the API is told the absolute instant either way.
  const byDay = useMemo(() => {
    const groups = new Map<string, FreeSlot[]>();
    for (const slot of slots ?? []) {
      const day = new Date(slot.start).toLocaleDateString(undefined, {
        weekday: "long",
        month: "short",
        day: "numeric",
      });
      groups.set(day, [...(groups.get(day) ?? []), slot]);
    }
    return [...groups];
  }, [slots]);

  async function confirm() {
    if (!chosen || !name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      setConfirmed(await booking.book({ name: name.trim(), email: email.trim(), start: chosen.start, minutes }));
    } catch (cause) {
      setError((cause as Error).message);
      // The slot may have gone while the form was open; reload what is left.
      booking.availability(minutes, DAYS).then(setSlots).catch(() => undefined);
      setChosen(null);
    } finally {
      setSaving(false);
    }
  }

  const clock = (iso: string) =>
    new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  if (confirmed) {
    return (
      <main id="main" className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
        <div className="w-full max-w-md rounded-xl border border-border bg-secondary/20 p-8 text-center">
          <div className="mx-auto mb-5 flex h-11 w-11 items-center justify-center rounded-full border border-border">
            <Check className="h-5 w-5" aria-hidden />
          </div>
          <h1 className="mb-2 font-serif text-2xl tracking-tight">You&apos;re booked</h1>
          <p className="tabular text-muted-foreground">
            {new Date(confirmed.start).toLocaleString(undefined, {
              weekday: "long",
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}{" "}
            – {clock(confirmed.end)}
          </p>
          {confirmed.rescheduled_blocks > 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              {confirmed.rescheduled_blocks} of {username}&apos;s flexible{" "}
              {confirmed.rescheduled_blocks === 1 ? "block" : "blocks"} moved to make room.
            </p>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-foreground selection:bg-primary selection:text-primary-foreground">
      <div className="w-full max-w-2xl rounded-xl border border-border bg-secondary/20 p-8 backdrop-blur-xl">
        <div className="mb-8 border-b border-border/50 pb-6">
          <h1 className="mb-2 font-serif text-3xl tracking-tight text-primary">
            Meet with {username}
          </h1>
          <p className="flex items-center gap-2 text-muted-foreground">
            <Globe className="h-4 w-4" aria-hidden /> Times shown in your own timezone
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <div>
            <h2 className="mb-4 text-lg font-medium text-primary">Available times</h2>

            <div className="mb-5 flex gap-2" role="group" aria-label="Meeting length">
              {LENGTHS.map((length) => (
                <button
                  key={length}
                  type="button"
                  onClick={() => setMinutes(length)}
                  aria-pressed={minutes === length}
                  className={`tabular rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                    minutes === length
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-muted-foreground hover:border-primary"
                  }`}
                >
                  {length}m
                </button>
              ))}
            </div>

            {error && (
              <p role="alert" className="mb-4 rounded-lg border border-border bg-background p-3 text-sm">
                {error}
              </p>
            )}

            {slots === null && !error && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Reading the calendar…
              </p>
            )}

            {slots !== null && slots.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Nothing open in the next {DAYS} days at this length. Try a shorter meeting.
              </p>
            )}

            <div className="max-h-80 space-y-5 overflow-y-auto pr-1">
              {byDay.map(([day, entries]) => (
                <div key={day}>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {day}
                  </h3>
                  <div className="space-y-2">
                    {entries.map((slot) => (
                      <button
                        key={slot.start}
                        type="button"
                        onClick={() => setChosen(slot)}
                        aria-pressed={chosen?.start === slot.start}
                        className={`group flex w-full items-center justify-between rounded-lg border p-3 transition-all ${
                          chosen?.start === slot.start
                            ? "border-primary bg-primary/5"
                            : "border-border bg-background hover:border-primary"
                        }`}
                      >
                        <span className="tabular font-medium">{clock(slot.start)}</span>
                        <span className="text-xs text-muted-foreground transition-colors group-hover:text-primary">
                          {chosen?.start === slot.start ? "Selected" : "Select"}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="mb-4 text-lg font-medium text-primary">Meeting details</h2>
            <div className="space-y-4 rounded-lg border border-border bg-background p-4">
              <div className="flex items-start gap-3">
                <Clock className="mt-0.5 h-5 w-5 text-muted-foreground" aria-hidden />
                <div>
                  <h3 className="tabular font-medium">{minutes} minute sync</h3>
                  <p className="text-sm text-muted-foreground">
                    General catch-up or introductory call.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <CalendarIcon className="mt-0.5 h-5 w-5 text-muted-foreground" aria-hidden />
                <div>
                  <h3 className="font-medium">Fluid scheduling</h3>
                  <p className="text-sm text-muted-foreground">
                    Focus time still shows as bookable. Taking a slot moves {username}&apos;s
                    flexible work rather than colliding with it.
                  </p>
                </div>
              </div>

              <div className="space-y-3 border-t border-border pt-4">
                <label className="block">
                  <span className="mb-1 block text-sm font-medium">Your name</span>
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    required
                    className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium">
                    Email <span className="text-muted-foreground">(optional)</span>
                  </span>
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </label>
                <button
                  type="button"
                  onClick={confirm}
                  disabled={!chosen || !name.trim() || saving}
                  className="h-11 w-full rounded-lg bg-primary text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40"
                >
                  {saving
                    ? "Booking…"
                    : chosen
                      ? `Book ${clock(chosen.start)}`
                      : "Pick a time first"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
