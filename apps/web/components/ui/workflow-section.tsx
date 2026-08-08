'use client'

import * as React from "react"
import { motion, type Variants } from "motion/react"
import Balancer from "react-wrap-balancer"
import { MessageSquare, Cpu, CalendarCheck } from "lucide-react"

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.15, delayChildren: 0.1 } },
}

const item: Variants = {
  hidden: { opacity: 0, y: 20, filter: 'blur(10px)' },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
}

const STEPS = [
  {
    icon: MessageSquare,
    title: "1. Natural Intent",
    description: "Type your raw intent exactly as you think it: 'I need to review the Q3 roadmap for 2 hours sometime before Friday'."
  },
  {
    icon: Cpu,
    title: "2. Edge Parsing",
    description: "Your local LLM safely translates the sentence into a rigid JSON constraint schema without ever seeing your calendar."
  },
  {
    icon: CalendarCheck,
    title: "3. Precision Placement",
    description: "The deterministic Python engine calculates the optimal slot within milliseconds, safely buffering around existing locks."
  }
]

export function WorkflowSection() {
  return (
    <section className="py-32 bg-secondary/20 overflow-hidden">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={container}
        >
          <motion.div variants={item} className="mb-20 text-center max-w-3xl mx-auto">
            <h2 className="font-serif text-[clamp(2.5rem,4vw,3.5rem)] text-foreground leading-[1.1] tracking-tight">
              <Balancer>Intelligence without compromise.</Balancer>
            </h2>
            <p className="mt-6 text-[18px] leading-[1.8] text-muted-foreground font-light text-balance">
              <Balancer>
                Experience the ease of AI scheduling without sacrificing the exactness of mathematical constraints.
              </Balancer>
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Connecting Line for Desktop */}
            <div className="hidden md:block absolute top-[52px] left-[15%] right-[15%] h-px bg-border z-0" />

            {STEPS.map((step, index) => {
              const Icon = step.icon
              return (
                <motion.div key={index} variants={item} className="relative z-10 flex flex-col items-center text-center">
                  <div className="mb-8 flex h-24 w-24 items-center justify-center rounded-full bg-background border border-border shadow-sm">
                    <Icon className="text-foreground" size={32} strokeWidth={1.5} />
                  </div>
                  <h3 className="font-serif text-[22px] text-foreground mb-4">{step.title}</h3>
                  <p className="text-[15px] leading-[1.7] text-muted-foreground font-light px-4">
                    {step.description}
                  </p>
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
