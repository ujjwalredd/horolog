/** A pulsing placeholder rectangle - the shared building block for a page's
 *  loading state. `prefers-reduced-motion` neutralises `animate-pulse`
 *  globally (see globals.css), so this needs no reduced-motion handling of
 *  its own. Compose a few of these, sized to roughly match the real layout,
 *  rather than leaving a blank gap or a plain "Loading..." string between
 *  mount and first data - the pattern `AnalyticsSkeleton` established. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-sunk ${className}`} />;
}
