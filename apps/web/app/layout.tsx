import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Vendored as real files under app/fonts/ rather than next/font/google:
// google's loader still fetches these .woff2s from fonts.gstatic.com at
// *build* time even though nothing touches it at runtime, so a build on a
// network-restricted CI runner (or any offline environment) fails outright —
// this happened for real. Vendoring the files means the build needs zero
// network access, ever. Weights match what was requested before, so nothing
// renders differently — see app/fonts/README.md for provenance if these
// ever need re-fetching (a new weight, a font update).
const jost = localFont({
  src: [
    { path: "./fonts/jost/jost-300.woff2", weight: "300", style: "normal" },
    { path: "./fonts/jost/jost-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/jost/jost-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/jost/jost-600.woff2", weight: "600", style: "normal" },
    { path: "./fonts/jost/jost-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-jost",
  display: "swap",
});
const bodoniModa = localFont({
  src: [
    { path: "./fonts/bodoni-moda/bodoni-moda-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/bodoni-moda/bodoni-moda-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/bodoni-moda/bodoni-moda-600.woff2", weight: "600", style: "normal" },
    { path: "./fonts/bodoni-moda/bodoni-moda-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-bodoni-moda",
  display: "swap",
});
const jetbrainsMono = localFont({
  src: [
    { path: "./fonts/jetbrains-mono/jetbrains-mono-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/jetbrains-mono/jetbrains-mono-500.woff2", weight: "500", style: "normal" },
  ],
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
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
