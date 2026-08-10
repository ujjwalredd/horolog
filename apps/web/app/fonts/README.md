# Vendored fonts

Jost, Bodoni Moda, and JetBrains Mono, all SIL Open Font License 1.1 —
freely redistributable, which is why the `.woff2` binaries are committed
here rather than fetched at build time.

They used to load via `next/font/google`, which still reaches out to
`fonts.gstatic.com` at build time even though nothing touches it at
runtime. That broke a real CI build on a network-restricted runner. Vendoring
means `npm run build` needs zero network access, in any environment.

To update a weight or add one: fetch the real `.woff2` from
`https://fonts.googleapis.com/css2?family=<Family>:wght@<weight>` with a
modern desktop browser `User-Agent` header (Google serves woff2 only to
UAs that support it), take the `latin` subset's `url()`, and place it here
following the existing `<family>-<weight>.woff2` naming. Update the `src`
array in `app/layout.tsx` to match.
