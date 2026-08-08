"use client";

import { useEffect, useRef } from "react";

/** The hero's living gradient.
 *
 *  Canvas rather than an animated SVG or a stack of CSS gradients: this draws
 *  ~40 stacked sine bands every frame, which CSS cannot express and SVG filters
 *  render far more expensively. It stays cheap by drawing at a fixed low
 *  resolution and letting the browser scale it up — the shapes are soft enough
 *  that nobody can tell, and the fill rate drops by ~10x.
 *
 *  Motion is slow on purpose (one full period is ~40 seconds). A hero that
 *  visibly animates reads as a demo; one that drifts reads as depth.
 */
export function Wave({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    // Respect the OS setting: render one static frame and stop. The gradient
    // still carries the visual weight; only the drift is removed.
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const W = 480;
    const H = 300;
    canvas.width = W;
    canvas.height = H;

    const BANDS = 42;
    const start = performance.now();
    let frame = 0;

    // Indigo → violet → warm sand. Three stops, low saturation at the edges,
    // so the wash never competes with the headline sitting on top of it.
    const stops: [number, number, number][] = [
      [79, 70, 229],
      [124, 92, 220],
      [196, 152, 168],
      [214, 186, 152],
    ];

    function mix(t: number): string {
      const scaled = t * (stops.length - 1);
      const i = Math.min(stops.length - 2, Math.floor(scaled));
      const f = scaled - i;
      const a = stops[i]!;
      const b = stops[i + 1]!;
      return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)}, ${Math.round(
        a[1] + (b[1] - a[1]) * f,
      )}, ${Math.round(a[2] + (b[2] - a[2]) * f)})`;
    }

    function draw(now: number) {
      const t = reduced ? 8 : (now - start) / 1000;
      ctx!.clearRect(0, 0, W, H);

      for (let i = 0; i < BANDS; i++) {
        const p = i / (BANDS - 1);
        ctx!.beginPath();
        ctx!.moveTo(0, H);

        for (let x = 0; x <= W; x += 8) {
          const u = x / W;
          // Three incommensurate frequencies so the surface never repeats
          // visibly within a session.
          const y =
            H * (0.34 + p * 0.5) +
            Math.sin(u * 5.1 + t * 0.16 + p * 2.9) * 26 * (1 - p * 0.45) +
            Math.sin(u * 2.3 - t * 0.11 + p * 1.7) * 34 * (1 - p * 0.3) +
            Math.sin(u * 9.7 + t * 0.07 + p * 4.2) * 7;
          ctx!.lineTo(x, y);
        }

        ctx!.lineTo(W, H);
        ctx!.closePath();
        // Bands are nearly transparent and overlap heavily; the density of the
        // stack is what produces the depth, not any single layer.
        ctx!.fillStyle = mix(p);
        ctx!.globalAlpha = 0.038 + (1 - p) * 0.028;
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;

      if (!reduced) frame = requestAnimationFrame(draw);
    }

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={`pointer-events-none h-full w-full ${className}`}
      style={{ filter: "blur(34px) saturate(1.1)", transform: "scale(1.15)" }}
    />
  );
}
