import * as React from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export interface CtaProps {
  ctaEnabled: boolean
  text: string
  link: string
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link"
}

export function Cta({ cta }: { cta: CtaProps }) {
  if (!cta.ctaEnabled) return null

  return (
    <Button variant={cta.variant || "default"} asChild>
      <Link href={cta.link || "#"}>
        {cta.text}
      </Link>
    </Button>
  )
}
