"use client";

import { useEffect, useRef, useState } from "react";

/** Fade-and-lift on first entry.
 *
 *  IntersectionObserver rather than a scroll library: this is the whole feature,
 *  it costs nothing, and it never runs work on the scroll thread. `once` is the
 *  default because content that re-animates every time it passes the viewport
 *  reads as a screensaver.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li" | "header";
}) {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setShown(true);
          observer.disconnect();
        }
      },
      // Fire a little before the element is fully on screen, so the motion has
      // finished by the time the reader's eye arrives.
      { rootMargin: "0px 0px -12% 0px", threshold: 0.05 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ref={ref as any}
      className={className}
      style={{
        opacity: shown ? 1 : 0,
        transform: shown ? "none" : "translateY(14px)",
        transition: `opacity 620ms cubic-bezier(0.16,1,0.3,1) ${delay}ms, transform 620ms cubic-bezier(0.16,1,0.3,1) ${delay}ms`,
      }}
    >
      {children}
    </Tag>
  );
}

/** Scroll progress through an element, 0 → 1, sampled on rAF.
 *
 *  Reads layout inside the frame callback rather than in the scroll handler, so
 *  measurement and paint stay in the same frame and never thrash.
 */
export function useScrollProgress(ref: React.RefObject<HTMLElement | null>): number {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    let running = true;

    function tick() {
      if (!running) return;
      const node = ref.current;
      if (node) {
        const rect = node.getBoundingClientRect();
        const span = rect.height - window.innerHeight;
        const value = span > 0 ? Math.min(1, Math.max(0, -rect.top / span)) : 0;
        setProgress((prev) => (Math.abs(prev - value) > 0.002 ? value : prev));
      }
      frame = requestAnimationFrame(tick);
    }

    frame = requestAnimationFrame(tick);
    return () => {
      running = false;
      cancelAnimationFrame(frame);
    };
  }, [ref]);

  return progress;
}
