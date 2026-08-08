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

const FAQS = [
  {
    question: "Do I need an OpenAI API key?",
    answer: "No. While Horolog supports OpenAI and Anthropic, it is built to run flawlessly with local LLMs like Llama 3 via Ollama. You can run the entire stack fully air-gapped on your own hardware."
  },
  {
    question: "Does the LLM have access to my calendar data?",
    answer: "Never. The LLM acts purely as a linguistic parser to generate a JSON schema of your intent (e.g. 'Gym for 1 hour'). The deterministic Python engine handles the actual schedule constraints and calendar data entirely separately."
  },
  {
    question: "How do I sync it with my work calendar?",
    answer: "Horolog supports CalDAV and direct ICS feeds. You can connect your Google Workspace, Microsoft Exchange, or Apple Calendar locally without exposing credentials to a third-party cloud."
  },
  {
    question: "Is this production ready for teams?",
    answer: "Horolog is designed as a single-player engine by default to guarantee absolute privacy. However, you can deploy it behind an SSO proxy (like Authelia or Tailscale) to share the instance securely across your organization."
  }
]

export function FaqSection() {
  return (
    <section className="py-32 bg-background overflow-hidden border-y border-border">
      <div className="mx-auto max-w-4xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={container}
        >
          <motion.div variants={item} className="mb-16 text-center">
            <h2 className="font-serif text-[clamp(2rem,4vw,3.5rem)] text-foreground leading-[1.1] tracking-tight">
              <Balancer>Frequently asked questions.</Balancer>
            </h2>
          </motion.div>

          <div className="space-y-6">
            {FAQS.map((faq, index) => (
              <motion.div key={index} variants={item} className="p-8 rounded-2xl bg-secondary/30 border border-border transition-colors hover:bg-secondary/50">
                <h3 className="text-[17px] font-semibold text-foreground mb-3">{faq.question}</h3>
                <p className="text-[15px] leading-relaxed text-muted-foreground font-light">
                  {faq.answer}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
