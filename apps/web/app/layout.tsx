import type { Metadata } from "next";
import { Bodoni_Moda, JetBrains_Mono, Jost } from "next/font/google";
import "./globals.css";

// Vendored at build time (next/font), not fetched from Google's CDN at
// runtime — "no telemetry, nothing leaves the machine" (login/page.tsx)
// should also be true of the UI's own asset loading. Weights match what the
// old <link>/@import tags requested, so nothing renders differently.
const jost = Jost({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-jost",
  display: "swap",
});
const bodoniModa = Bodoni_Moda({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-bodoni-moda",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Horolog - Defend Your Focus Time",
    template: "%s | Horolog",
  },
  description: "An open-source, self-hosted AI calendar auto-scheduler that defends your focus time, habits, and tasks.",
  keywords: [
    "calendar",
    "auto-scheduler",
    "ai calendar",
    "reclaim alternative",
    "focus time",
    "time blocking",
    "productivity",
    "self-hosted",
  ],
  authors: [{ name: "Horolog Contributors" }],
  openGraph: {
    title: "Horolog - Defend Your Focus Time",
    description: "An open-source, self-hosted AI calendar that defends your time.",
    type: "website",
    siteName: "Horolog",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${jost.variable} ${bodoniModa.variable} ${jetbrainsMono.variable}`}
    >
      <body>
        <a
          href="#planner"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
        >
          Skip to planner
        </a>
        {children}
      </body>
    </html>
  );
}
