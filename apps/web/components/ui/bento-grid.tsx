'use client'

import * as React from "react"
import { motion, type Variants } from "motion/react"
import { cn } from "@/lib/utils"
import Balancer from "react-wrap-balancer"
import { Brain, Cpu, UploadCloud, Link, GitPullRequest } from "lucide-react"

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

export function BentoGrid() {
  return (
    <section id="manifesto" className="relative py-32 bg-sunk overflow-hidden">
      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={container}
        >
          <motion.div variants={item} className="mb-20 text-center max-w-3xl mx-auto">
            <h2 className="font-serif text-[clamp(2.5rem,5vw,4.5rem)] leading-[1.05] text-foreground tracking-tight text-balance">
              <Balancer>One primitive. Infinite possibilities.</Balancer>
            </h2>
            <p className="mt-8 text-[18px] leading-[1.8] text-muted-foreground font-light text-balance">
              <Balancer>
                Traditional calendars isolate your tasks, habits, and meetings into rigid silos. Everything on your schedule competes for time honestly, orchestrated by an intelligent solver.
              </Balancer>
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[280px]">
            {/* Bento Box 1 */}
            <motion.div variants={item} className="md:col-span-2 group flex flex-col p-10 rounded-3xl bg-background shadow-sm hover:shadow-md border border-primary/5 transition-shadow duration-300">
              <div className="mb-6 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/5 transition-colors duration-500 group-hover:bg-primary/10">
                <Brain className="text-primary" size={28} strokeWidth={1.5} />
              </div>
              <h3 className="font-serif text-[28px] text-foreground mb-4">Cognitive Scheduling</h3>
              <p className="text-[16px] leading-[1.7] text-muted-foreground font-light max-w-md">
                Tell the engine &apos;deep work for 4 hours this week&apos;. It carves the optimal slots around your existing commitments and adapts dynamically.
              </p>
            </motion.div>

            {/* Bento Box 2 */}
            <motion.div variants={item} className="md:row-span-2 group flex flex-col p-10 rounded-3xl bg-primary text-white shadow-xl">
              <div className="mb-8 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10">
                <Cpu className="text-white" size={28} strokeWidth={1.5} />
              </div>
              <h3 className="font-serif text-[32px] mb-4 leading-tight">Local-First<br/>Execution</h3>
              <p className="text-[16px] leading-[1.7] text-white/70 font-light mt-auto">
                Point it at Claude, OpenAI, or a local Llama instance. Complete privacy, absolute control. Zero cloud egress.
              </p>
            </motion.div>

            {/* Bento Box 3 */}
            <motion.div variants={item} className="group flex flex-col p-8 rounded-3xl bg-background shadow-sm hover:shadow-md border border-primary/5 transition-shadow duration-300">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/5 transition-colors duration-500 group-hover:bg-primary/10">
                <Link className="text-primary" size={24} strokeWidth={1.5} />
              </div>
              <h3 className="font-serif text-[22px] text-foreground mb-3">Smart Booking Links</h3>
              <p className="text-[15px] leading-[1.6] text-muted-foreground font-light">
                Public booking links (`/book/[username]`) that dynamically protect your deep focus time.
              </p>
            </motion.div>

            {/* Bento Box 4 */}
            <motion.div variants={item} className="group flex flex-col p-8 rounded-3xl bg-background shadow-sm hover:shadow-md border border-primary/5 transition-shadow duration-300">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/5 transition-colors duration-500 group-hover:bg-primary/10">
                <UploadCloud className="text-primary" size={24} strokeWidth={1.5} />
              </div>
              <h3 className="font-serif text-[22px] text-foreground mb-3">Real Calendar Write-Back</h3>
              <p className="text-[15px] leading-[1.6] text-muted-foreground font-light">
                Push scheduled blocks onto a dedicated calendar on Google or Outlook as real events — colleagues see them, and can&apos;t double-book over them.
              </p>
            </motion.div>

            {/* Bento Box 5 */}
            <motion.div variants={item} className="md:col-span-2 group flex flex-col p-8 rounded-3xl bg-background shadow-sm hover:shadow-md border border-primary/5 transition-shadow duration-300">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/5 transition-colors duration-500 group-hover:bg-primary/10">
                <GitPullRequest className="text-primary" size={24} strokeWidth={1.5} />
              </div>
              <h3 className="font-serif text-[22px] text-foreground mb-3">Third-Party Task Sync</h3>
              <p className="text-[15px] leading-[1.6] text-muted-foreground font-light">
                Sync Linear, Todoist & GitHub issues directly into Horolog. They automatically schedule as fluid tasks around your real-life calendar.
              </p>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
