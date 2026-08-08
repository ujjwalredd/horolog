'use client'

import * as React from "react"
import { motion, type Variants } from "motion/react"
import Balancer from "react-wrap-balancer"

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

export function TechnicalSection() {
  return (
    <section className="py-32 bg-secondary/20 overflow-hidden border-y border-primary/5">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={container}
        >
          <motion.div variants={item} className="mb-20 text-center max-w-3xl mx-auto">
            <h2 className="font-serif text-[clamp(2.5rem,5vw,4.5rem)] text-primary leading-[1.05] tracking-tight text-balance">
              <Balancer>Engineered for absolute control.</Balancer>
            </h2>
            <p className="mt-6 text-[18px] leading-[1.8] text-muted-foreground font-light text-balance">
              <Balancer>
                Horolog is not a black box. It separates natural language processing from the actual calendar mathematics, ensuring deterministic constraint solving without LLM hallucinations.
              </Balancer>
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <motion.div variants={item} className="p-10 rounded-3xl bg-background shadow-sm hover:shadow-md border border-primary/5 transition-shadow duration-300">
              <h3 className="font-serif text-[24px] text-primary mb-4">Schema-Constrained LLM Layer</h3>
              <p className="text-[15px] leading-[1.7] text-muted-foreground font-light mb-6">
                When you input an intent, it is routed through an LLM layer (OpenAI, Anthropic, or your local Ollama) using strict structured outputs. The model never touches your calendar; it only emits a JSON schema defining the priority, boundaries, and duration of the task.
              </p>
              <div className="rounded-xl bg-primary p-5 text-white/90 text-[13px] font-mono leading-[1.6] overflow-x-auto">
                <code>
                  HOROLOG_LLM_PROVIDER=ollama<br/>
                  HOROLOG_LLM_MODEL=llama3:8b<br/>
                  HOROLOG_LLM_BASE_URL=http://localhost:11434
                </code>
              </div>
            </motion.div>

            <motion.div variants={item} className="p-10 rounded-3xl bg-background shadow-sm hover:shadow-md border border-primary/5 transition-shadow duration-300">
              <h3 className="font-serif text-[24px] text-primary mb-4">Deterministic Constraint Solver</h3>
              <p className="text-[15px] leading-[1.7] text-muted-foreground font-light mb-6">
                The structured intent is passed to a high-performance, deterministic Python constraint solver running on FastAPI. It calculates the exact free slots across connected integrations, respecting pre-existing locks, meeting buffers, and user-defined constraints.
              </p>
              <ul className="space-y-3 text-[14px] text-muted-foreground font-light">
                <li className="flex items-center gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-accent" /> Millisecond resolution time
                </li>
                <li className="flex items-center gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-accent" /> Complete avoidance of LLM hallucination
                </li>
                <li className="flex items-center gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-accent" /> Mathematical guarantee of non-overlapping bounds
                </li>
              </ul>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
