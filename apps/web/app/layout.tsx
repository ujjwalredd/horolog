import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Horolog",
  description: "Open-source AI calendar that defends your time.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Self-host these for an air-gapped deploy; the CSS falls back to the
            system stack, so a blocked CDN degrades rather than breaks. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
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
