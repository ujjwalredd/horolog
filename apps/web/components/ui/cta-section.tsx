'use client'

import * as React from "react"
import { motion, type Variants } from "motion/react"
import Balancer from "react-wrap-balancer"
import { Button } from "@/components/ui/button"
import Link from "next/link"

const item: Variants = {
  hidden: { opacity: 0, y: 12, filter: 'blur(6px)' },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] },
  },
}

export function CtaSection({ title, description, link }: { title: string, description: string, link: string }) {
  return (
    <section className="relative overflow-hidden bg-background py-32 border-t border-primary/10">
      <div className="relative mx-auto max-w-4xl px-6 text-center z-10">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
          className="flex flex-col items-center justify-center"
        >
          <motion.h2 variants={item} className="font-serif text-[clamp(3rem,6vw,5.5rem)] text-foreground leading-tight tracking-tight text-balance">
            <Balancer>{title}</Balancer>
          </motion.h2>
          
          <motion.p variants={item} className="mx-auto mt-8 max-w-xl text-[18px] font-light leading-relaxed text-muted-foreground text-balance">
            <Balancer>{description}</Balancer>
          </motion.p>
          
          <motion.div variants={item} className="mt-12 flex flex-wrap items-center justify-center gap-5">
            <Button size="lg" className="rounded-full px-10 h-14 text-base" asChild>
              <Link href={link}>Access Platform</Link>
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}
