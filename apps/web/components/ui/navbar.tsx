'use client'

import * as React from "react"
import Link from "next/link"
import { Hexagon } from "lucide-react"
import { motion } from "motion/react"
import { Button } from "@/components/ui/button"

export function Navbar() {
  return (
    <motion.header 
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="fixed top-0 left-0 right-0 z-50 border-b border-primary/5 bg-background/80 backdrop-blur-2xl"
    >
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 text-primary hover:opacity-80 transition-opacity">
          <Hexagon className="h-6 w-6" />
          <span className="font-serif text-[22px] tracking-wide">Horolog</span>
        </Link>
        <div className="flex items-center gap-6">
          <Link
            href="#manifesto"
            className="hidden text-[14px] font-medium text-muted-foreground transition-colors hover:text-primary sm:block tracking-wide"
          >
            Features
          </Link>
          <Button variant="default" className="rounded-full px-6" asChild>
            <Link href="/login">Sign In</Link>
          </Button>
        </div>
      </div>
    </motion.header>
  )
}
