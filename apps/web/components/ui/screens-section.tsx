'use client'

import * as React from "react"
import { motion, type Variants } from "motion/react"
import Balancer from "react-wrap-balancer"
import { Expand } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1, delayChildren: 0.1 } },
}

const item: Variants = {
  hidden: { opacity: 0, y: 20, filter: 'blur(10px)' },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
}

interface Screen {
  file: string
  name: string
  description: string
}

const PLANNER: Screen = {
  file: "planner",
  name: "Planner",
  description: "Month, week, day or list. Priority by accent weight, kind by glyph, movability by rule style. Live over SSE.",
}

const SCREENS: Screen[] = [
  {
    file: "inbox",
    name: "Task inbox",
    description: "Every intent and where it actually landed. Anything that did not fit is called out, not hidden.",
  },
  {
    file: "habits",
    name: "Habits & Focus Time",
    description: "Routines and weekly focus goals in the units people speak: ‘3× a week, an hour each, between 10 and 4’.",
  },
  {
    file: "meetings",
    name: "Meetings",
    description: "A Smart Meeting only lands where every attendee's busy time allows, without ever blocking your own solo work.",
  },
  {
    file: "analytics",
    name: "Analytics",
    description: "Stat tiles plus a per-day load chart. Palette validated for colour-vision deficiency, not eyeballed.",
  },
  {
    file: "connect",
    name: "Calendars",
    description: "Connect Google or Outlook, an ICS feed, or a CalDAV server; export your plan as a subscribable feed.",
  },
  {
    file: "time",
    name: "Time",
    description: "A live ‘today’ view: what's happening right now, what's next, and a moving now-line on the day's timeline.",
  },
]

function ScreenCard({ screen, featured = false }: { screen: Screen; featured?: boolean }) {
  return (
    <Dialog>
      <motion.figure
        variants={item}
        className={`group overflow-hidden rounded-2xl border border-primary/10 bg-sunk/40 shadow-sm transition-shadow duration-300 hover:shadow-md ${featured ? "rounded-3xl" : ""}`}
      >
        <DialogTrigger asChild>
          <button
            type="button"
            aria-label={`View ${screen.name} screenshot full size`}
            className="relative block w-full cursor-zoom-in text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          >
            <img
              src={`/screenshots/${screen.file}.png`}
              alt={`Horolog ${screen.name.toLowerCase()} view`}
              loading="lazy"
              decoding="async"
              width={1440}
              height={900}
              className="aspect-[8/5] w-full object-cover object-top transition-transform duration-300 ease-out group-hover:scale-[1.03]"
            />
            <span className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all duration-300 group-hover:bg-black/10 group-hover:opacity-100">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-background/90 px-3 py-1.5 text-[12px] font-medium text-foreground shadow-sm backdrop-blur-sm">
                <Expand size={13} strokeWidth={2} />
                View full size
              </span>
            </span>
          </button>
        </DialogTrigger>
        <figcaption className={featured ? "p-6" : "p-5"}>
          <span className={featured ? "text-[16px] font-semibold text-foreground" : "text-[15px] font-semibold text-foreground"}>
            {screen.name}
          </span>
          <p className={featured ? "mt-1 inline text-[14px] text-muted-foreground font-light" : "mt-1 text-[13px] leading-[1.6] text-muted-foreground font-light"}>
            {featured ? ` ${screen.description}` : screen.description}
          </p>
        </figcaption>
      </motion.figure>

      <DialogContent className="max-w-4xl gap-3 overflow-hidden border-primary/10 bg-background p-0 sm:rounded-2xl">
        <div className="p-6 pb-0">
          <DialogTitle className="font-serif text-xl font-normal text-foreground">{screen.name}</DialogTitle>
          <DialogDescription className="mt-1 text-[14px]">{screen.description}</DialogDescription>
        </div>
        <img
          src={`/screenshots/${screen.file}.png`}
          alt={`Horolog ${screen.name.toLowerCase()} view, full size`}
          decoding="async"
          width={1440}
          height={900}
          className="w-full"
        />
      </DialogContent>
    </Dialog>
  )
}

export function ScreensSection() {
  return (
    <section className="relative py-32 bg-background overflow-hidden">
      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={container}
        >
          <motion.div variants={item} className="mb-16 max-w-2xl">
            <span className="text-[13px] font-semibold uppercase tracking-wider text-primary">
              The real thing
            </span>
            <h2 className="mt-3 font-serif text-[clamp(2.25rem,4.5vw,3.75rem)] leading-[1.05] text-foreground tracking-tight">
              <Balancer>Not a mockup.</Balancer>
            </h2>
            <p className="mt-6 text-[17px] leading-[1.75] text-muted-foreground font-light">
              <Balancer>
                Real captures, from <code className="font-mono text-[0.9em]">npm run seed:demo</code>&apos;s sample week.
              </Balancer>
            </p>
          </motion.div>

          <div className="mb-6">
            <ScreenCard screen={PLANNER} featured />
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {SCREENS.map((screen) => (
              <ScreenCard key={screen.file} screen={screen} />
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
