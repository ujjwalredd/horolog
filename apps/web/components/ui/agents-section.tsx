'use client'

import * as React from "react"
import { motion, type Variants } from "motion/react"
import Balancer from "react-wrap-balancer"
import {
  Target,
  RotateCcw,
  Users,
  ListChecks,
  CalendarSync,
  BarChart3,
  Timer,
  Link2,
} from "lucide-react"

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
}

const item: Variants = {
  hidden: { opacity: 0, y: 16, filter: 'blur(8px)' },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
}

const AGENTS = [
  {
    icon: Target,
    name: "Smart Task Scheduler",
    description: "Deadline-aware tasks, split across sittings and placed around real meetings. Priority P1-P4 decides who wins a contested slot.",
  },
  {
    icon: RotateCcw,
    name: "Habit & Routine Manager",
    description: "‘Gym three times a week between 10 and 4.’ Recurrence, time-of-day windows, per-day caps, automatic relocation.",
  },
  {
    icon: CalendarSync,
    name: "Dynamic Calendar Sync",
    description: "ICS feeds, CalDAV servers, and real OAuth connections to Google Calendar and Outlook — recurring events expanded, free time ignored.",
  },
  {
    icon: Users,
    name: "Smart Meetings",
    description: "Multi-attendee scheduling that intersects everyone's availability — without letting a colleague's calendar block your own solo work.",
  },
  {
    icon: BarChart3,
    name: "Productivity Analytics",
    description: "Deep-work hours, meeting load, fragmentation, longest free run per day, after-hours load, unmet demand — all measured, not guessed.",
  },
  {
    icon: Timer,
    name: "Decompression Buffers",
    description: "Recovery time held after every substantial meeting, from any source. A run of back-to-back meetings gets one buffer, at the end.",
  },
  {
    icon: Link2,
    name: "Booking Links",
    description: "A public /book/name page offering true free time — hours holding flexible work stay bookable, because taking the slot moves it.",
  },
  {
    icon: ListChecks,
    name: "Tracker Integrations",
    description: "Linear, Todoist and GitHub issues pulled in as fluid tasks — via OAuth or a pasted personal key, scheduled around everything else.",
  },
]

export function AgentsSection() {
  return (
    <section id="agents" className="relative py-32 bg-background overflow-hidden">
      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={container}
        >
          <motion.div variants={item} className="mb-16 max-w-2xl">
            <span className="text-[13px] font-semibold uppercase tracking-wider text-primary">
              The full roster
            </span>
            <h2 className="mt-3 font-serif text-[clamp(2.25rem,4.5vw,3.75rem)] leading-[1.05] text-foreground tracking-tight">
              <Balancer>Eight agents. One engine underneath.</Balancer>
            </h2>
            <p className="mt-6 text-[17px] leading-[1.75] text-muted-foreground font-light">
              <Balancer>
                Every one of these is the same scheduling primitive wearing a different hat —
                a task, a habit and a meeting are all just demands for time with different rules.
                Nothing here is a separate subsystem that can drift out of sync with the rest.
              </Balancer>
            </p>
          </motion.div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {AGENTS.map((agent) => (
              <motion.div
                key={agent.name}
                variants={item}
                className="group flex flex-col rounded-2xl border border-primary/10 bg-sunk/40 p-6 transition-colors duration-300 hover:border-primary/20 hover:bg-sunk/70"
              >
                <div className="mb-5 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary/5 transition-colors duration-500 group-hover:bg-primary/10">
                  <agent.icon className="text-primary" size={20} strokeWidth={1.5} />
                </div>
                <h3 className="mb-2.5 text-[16px] font-semibold text-foreground">{agent.name}</h3>
                <p className="text-[13.5px] leading-[1.6] text-muted-foreground font-light">
                  {agent.description}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
