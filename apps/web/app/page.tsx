import Link from "next/link";
import { Glyph } from "@/app/components/Glyph";
import { Reveal } from "@/app/components/Reveal";
import { StabilityDemo } from "@/app/components/StabilityDemo";
import { Wave } from "@/app/components/Wave";

/* Every figure on this page comes from `python -m horolog.bench` on the
   committed engine. Nothing here is aspirational, and there are no invented
   customer logos or testimonials — an open-source project that fabricates
   social proof has already told you what it is. */
const METRICS = [
  { value: "3ms", label: "to re-plan a week", note: "p50, 30 intents" },
  { value: "97ms", label: "at 300 intents", note: "p95, 21-day horizon" },
  { value: "0", label: "blocks moved needlessly", note: "verified by test" },
  { value: "100%", label: "runs on your hardware", note: "no egress" },
];

const AGENTS = [
  {
    kind: "focus" as const,
    title: "Focus time",
    body: "Set an hours-per-week goal. It carves and defends the blocks, and re-carves them when your week changes.",
  },
  {
    kind: "habit" as const,
    title: "Habits",
    body: "“Gym three times a week, between 10 and 4.” It picks the slots, and moves them when a meeting lands on one.",
  },
  {
    kind: "task" as const,
    title: "Tasks",
    body: "Deadline-aware and splittable. Long work is chunked across sittings; short work stays in one piece.",
  },
  {
    kind: "buffer" as const,
    title: "Buffers",
    body: "Decompression after calls, prep before the meetings that need it, travel time where it matters.",
  },
  {
    kind: "meeting" as const,
    title: "Smart meetings",
    body: "Recurring syncs that re-negotiate their slot against everyone's real availability instead of sitting stale.",
  },
];

const PROVIDERS = [
  { name: "Ollama", detail: "llama, qwen, deepseek — on your laptop", tag: "local" },
  { name: "vLLM / SGLang", detail: "your own GPU box or cluster", tag: "local" },
  { name: "Anthropic", detail: "Claude, via the official SDK", tag: "hosted" },
  { name: "OpenAI", detail: "and any OpenAI-compatible endpoint", tag: "hosted" },
];

export default function Landing() {
  return (
    // No `overflow-x-hidden` here: it computes `overflow-y: auto`, which makes
    // this a scroll container and silently breaks `position: sticky` for every
    // descendant — including the pinned scroll demo. Horizontal overflow is
    // prevented on `html` in globals.css instead, where it does no such damage.
    <div>
      <Nav />

      {/* ---------------------------------------------------------------- Hero */}
      <header className="relative isolate">
        <div className="pointer-events-none absolute inset-x-0 -top-32 -z-10 h-[620px] opacity-[0.55]">
          <Wave />
        </div>
        <div className="pointer-events-none absolute inset-x-0 top-[420px] -z-10 h-64 bg-gradient-to-b from-transparent to-bg" />

        <div className="mx-auto max-w-5xl px-6 pb-24 pt-28 text-center sm:pt-36">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border bg-surface/80 px-3.5 py-1.5 text-[12px] text-fg-muted shadow-sm backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-ok" />
              Open source · AGPL · self-hosted
            </span>
          </Reveal>

          <Reveal delay={80}>
            <h1 className="mt-7 text-balance text-[clamp(2.6rem,7vw,5.2rem)] font-semibold leading-[0.98] tracking-tight-optical">
              Your calendar should
              <br />
              defend your time.
            </h1>
          </Reveal>

          <Reveal delay={160}>
            <p className="mx-auto mt-6 max-w-xl text-balance text-[17px] leading-relaxed text-fg-muted">
              Horolog places focus time, habits and tasks around the meetings you
              actually have — then keeps them there. Runs entirely on your own
              machine, with whichever model you already trust.
            </p>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/login"
                className="group inline-flex h-11 items-center gap-2 rounded-lg bg-accent px-6 text-[14px] font-medium text-on-accent shadow-md transition-all duration-200 hover:bg-accent-hover hover:shadow-pop"
              >
                Open the planner
                <span className="transition-transform duration-200 group-hover:translate-x-0.5">
                  →
                </span>
              </Link>
              <a
                href="#how"
                className="inline-flex h-11 items-center rounded-lg border bg-surface px-6 text-[14px] font-medium shadow-sm transition-colors duration-200 hover:bg-sunk"
              >
                See how it plans
              </a>
            </div>
          </Reveal>

          <Reveal delay={320}>
            <p className="tabular mt-5 text-[12px] text-fg-muted">
              docker compose up · no account · no telemetry
            </p>
          </Reveal>
        </div>
      </header>

      {/* ------------------------------------------------------------- Metrics */}
      <section className="border-y bg-surface/60">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-px bg-line lg:grid-cols-4">
          {METRICS.map((metric, i) => (
            <Reveal
              key={metric.label}
              delay={i * 70}
              className="bg-bg px-6 py-8 text-center"
            >
              <div className="tabular text-[30px] font-semibold leading-none">
                {metric.value}
              </div>
              <div className="mt-2 text-[13px] text-fg">{metric.label}</div>
              <div className="tabular mt-1 text-[11px] text-fg-muted">{metric.note}</div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------- Scroll-driven proof */}
      <section id="how">
        <StabilityDemo />
      </section>

      {/* -------------------------------------------------------- One primitive */}
      <section className="border-t bg-surface/60 py-24">
        <div className="mx-auto max-w-5xl px-6">
          <Reveal className="mb-14 max-w-2xl">
            <p className="mb-3 text-[12px] font-medium uppercase tracking-[0.14em] text-accent">
              Five features, one engine
            </p>
            <h2 className="text-[clamp(1.9rem,4vw,3rem)] font-semibold leading-[1.08]">
              Everything on your calendar is the same shape.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-fg-muted">
              A duration, a window it may land in, how finely it can be split, and how
              much it matters. Focus time, habits, tasks, buffers and meetings are that
              one primitive wearing five hats — which is why they compete for time
              honestly instead of each defending their own turf.
            </p>
          </Reveal>

          <div className="grid gap-px overflow-hidden rounded-card border bg-line sm:grid-cols-2 lg:grid-cols-3">
            {AGENTS.map((agent, i) => (
              <Reveal key={agent.title} delay={i * 60} className="group bg-surface p-7">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-accent/8 text-accent transition-colors duration-200 group-hover:bg-accent/14">
                  <Glyph kind={agent.kind} size={17} />
                </span>
                <h3 className="mt-4 text-[16px] font-medium">{agent.title}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-fg-muted">{agent.body}</p>
              </Reveal>
            ))}
            <Reveal delay={300} className="flex flex-col justify-center bg-sunk p-7">
              <p className="text-[13px] leading-relaxed text-fg-muted">
                Because they share an engine, a critical task can take a slot from a
                low-priority habit — but nothing, at any priority, can move a meeting
                you actually agreed to.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ Bring your model */}
      <section className="py-24">
        <div className="mx-auto grid max-w-5xl gap-14 px-6 lg:grid-cols-2 lg:items-center">
          <Reveal>
            <p className="mb-3 text-[12px] font-medium uppercase tracking-[0.14em] text-accent">
              Bring your own model
            </p>
            <h2 className="text-[clamp(1.9rem,4vw,3rem)] font-semibold leading-[1.08]">
              Point it at any model.
              <br />
              <span className="text-fg-muted">Change one line.</span>
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-fg-muted">
              The model only ever fills in a form — it reads “gym three times a week
              between 10 and 4” and produces a schema-checked request. It never picks a
              time, and it cannot write to your calendar. The scheduler does that, from
              your real availability.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-fg-muted">
              Output is constrained at decode time, so malformed answers aren’t
              caught — they’re impossible.
            </p>
          </Reveal>

          <Reveal delay={120}>
            <div className="overflow-hidden rounded-card border bg-surface shadow-md">
              <div className="flex items-center gap-2 border-b bg-sunk px-4 py-2.5">
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
                <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
                <span className="tabular ml-2 text-[11px] text-fg-muted">.env</span>
              </div>
              <pre className="tabular overflow-x-auto px-5 py-4 text-[12.5px] leading-relaxed">
                <code>
                  <span className="text-fg-muted"># local, zero cost</span>
                  {"\n"}HOROLOG_LLM_PROVIDER=<span className="text-accent">openai</span>
                  {"\n"}HOROLOG_LLM_BASE_URL=<span className="text-accent">
                    http://localhost:11434/v1
                  </span>
                  {"\n"}HOROLOG_LLM_MODEL=<span className="text-accent">qwen3:8b</span>
                  {"\n\n"}
                  <span className="text-fg-muted"># or Claude</span>
                  {"\n"}HOROLOG_LLM_PROVIDER=<span className="text-accent">anthropic</span>
                  {"\n"}HOROLOG_LLM_MODEL=<span className="text-accent">claude-opus-5</span>
                </code>
              </pre>
              <ul className="divide-y border-t">
                {PROVIDERS.map((provider) => (
                  <li key={provider.name} className="flex items-center gap-3 px-5 py-3">
                    <span
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                        provider.tag === "local" ? "bg-ok" : "bg-accent"
                      }`}
                    />
                    <span className="text-[13px] font-medium">{provider.name}</span>
                    <span className="truncate text-[12px] text-fg-muted">
                      {provider.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------ Final CTA */}
      <section className="relative isolate overflow-hidden border-t">
        <div className="pointer-events-none absolute inset-x-0 -bottom-40 -z-10 h-[460px] opacity-40">
          <Wave />
        </div>
        <div className="mx-auto max-w-3xl px-6 py-28 text-center">
          <Reveal>
            <h2 className="text-balance text-[clamp(2rem,5vw,3.4rem)] font-semibold leading-[1.05]">
              Get your week back.
            </h2>
            <p className="mx-auto mt-5 max-w-lg text-balance text-[16px] leading-relaxed text-fg-muted">
              Clone it, run it, keep your calendar on your own machine. No seats, no
              trial, nothing phoning home.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/login"
                className="inline-flex h-11 items-center rounded-lg bg-accent px-6 text-[14px] font-medium text-on-accent shadow-md transition-all duration-200 hover:bg-accent-hover hover:shadow-pop"
              >
                Open the planner
              </Link>
              <a
                href="https://github.com"
                className="inline-flex h-11 items-center rounded-lg border bg-surface px-6 text-[14px] font-medium shadow-sm transition-colors duration-200 hover:bg-sunk"
              >
                Read the source
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t bg-surface/60">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-8">
          <span className="text-[13px] text-fg-muted">
            Horolog — an open-source AI calendar.
          </span>
          <span className="tabular text-[12px] text-fg-muted">AGPL-3.0</span>
        </div>
      </footer>
    </div>
  );
}

function Nav() {
  return (
    <nav className="sticky top-0 z-40 border-b bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <Mark />
          <span className="text-[15px] font-semibold tracking-tight-optical">Horolog</span>
        </Link>
        <div className="flex items-center gap-1">
          <a
            href="#how"
            className="hidden h-9 items-center rounded-md px-3 text-[13px] text-fg-muted transition-colors duration-150 hover:bg-sunk hover:text-fg sm:inline-flex"
          >
            How it plans
          </a>
          <Link
            href="/login"
            className="inline-flex h-9 items-center rounded-md bg-fg px-4 text-[13px] font-medium text-bg transition-opacity duration-150 hover:opacity-90"
          >
            Open planner
          </Link>
        </div>
      </div>
    </nav>
  );
}

/** A clock face reduced to its two hands — the whole product is "where should
 *  this hour go", so the mark is an hour and a minute hand and nothing else. */
function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9.25" stroke="var(--color-fg)" strokeWidth="1.5" />
      <path
        d="M12 6.75V12l3.4 2.1"
        stroke="var(--color-accent)"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
