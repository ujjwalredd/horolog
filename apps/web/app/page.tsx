import { Marquee } from "@/app/components/Marquee"
import { CheckCircle2, Hexagon } from "lucide-react"

import { Navbar } from "@/components/ui/navbar"
import { Hero05 } from "@/components/ui/hero-05"
import { AgentsSection } from "@/components/ui/agents-section"
import { BentoGrid } from "@/components/ui/bento-grid"
import { TechnicalSection } from "@/components/ui/technical-section"
import { WorkflowSection } from "@/components/ui/workflow-section"
import { FaqSection } from "@/components/ui/faq-section"
import { CtaSection } from "@/components/ui/cta-section"
import { Footer } from "@/components/ui/footer"

const INTEGRATIONS = [
  "Google Calendar", "Outlook / Exchange", "Apple Calendar", "iCalendar", "CalDAV",
  "Linear", "Todoist", "GitHub", "Notion", "ClickUp", "Jira", "Zoom",
]

const GithubIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
)

const GITHUB_URL = "https://github.com/ujjwalredd/horolog"

// Set by Vercel on every build and request there, never locally or in the
// Docker image — this deployment has no backend behind it, so every button
// that would otherwise open the app points at the source instead.
const LANDING_ONLY = process.env.VERCEL === "1"
const appHref = LANDING_ONLY ? GITHUB_URL : "/login"

export default function Landing() {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <Navbar signInHref={appHref} />

      <Hero05
        tagline="The Engine of Time"
        title="Defend your deep work."
        description="Horolog is a premier, self-hosted AI calendar engine. It treats tasks, habits, and focus time as fluid primitives-weaving them beautifully around your hard commitments."
        landscapeImage="https://images.unsplash.com/photo-1475924156734-496f6cac6ec1?q=80&w=1144&auto=format&fit=crop"
        landscapeAlt="Calm nature landscape representing peace of mind"
        animation="subtle"
        primaryCTA={{
          ctaEnabled: true,
          text: LANDING_ONLY ? 'View on GitHub' : 'Enter the Planner',
          link: appHref,
          variant: 'default',
        }}
        secondaryCTA={{
          ctaEnabled: true,
          text: 'Read the Manifesto',
          link: '#manifesto',
          variant: 'outline',
        }}
      />

      <section className="border-y border-primary/10 bg-background relative z-10 overflow-hidden py-6">
        <Marquee className="[--duration:30s]" pauseOnHover>
          {INTEGRATIONS.map((integration) => (
            <div key={integration} className="flex items-center gap-2 mx-8 text-muted-foreground font-medium text-[15px] hover:text-primary transition-colors">
              <CheckCircle2 size={16} className="text-primary" />
              {integration}
            </div>
          ))}
        </Marquee>
      </section>

      <WorkflowSection />
      <AgentsSection />
      <TechnicalSection />
      <BentoGrid />
      <FaqSection />

      <CtaSection
        title="Reclaim your sovereignty."
        description="Download the engine. Run it on your hardware. Stop renting your calendar."
        link={appHref}
      />

      <Footer
        logo={<Hexagon className="h-8 w-8 text-primary" />}
        brandName="Horolog"
        socialLinks={[
          {
            icon: <GithubIcon className="h-4 w-4" />,
            href: "https://github.com/ujjwalredd/horolog",
            label: "GitHub",
          },
        ]}
        mainLinks={[]}
        legalLinks={[]}
        copyright={{
          text: "© 2026 Horolog Contributors.",
          license: "Released under AGPL-3.0 License",
        }}
      />
    </div>
  )
}
