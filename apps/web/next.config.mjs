import path from "node:path";

const api = process.env.HOROLOG_API_URL ?? "http://localhost:8000";

/** @type {import('next').NextConfig} */
const config = {
  // Pin the workspace root. Without this Next walks up looking for a lockfile
  // and can land on one in the home directory, which makes it trace the wrong
  // tree and print a warning on every start.
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),

  // Opening the dev server from another device on the LAN otherwise warns on
  // every asset request.
  allowedDevOrigins: ["localhost", "127.0.0.1", "10.0.0.0/8", "192.168.0.0/16"],

  // Proxy the API through this origin so the browser only ever talks to one
  // host: no CORS, and SSE needs no preflight.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },

  eslint: {
    // `next build` runs its own lint pass and now finds a real config
    // (eslint.config.mjs, added so `npm run lint` doesn't hang on Next's
    // interactive setup wizard instead of failing cleanly). That surfaced
    // pre-existing lint errors across the app unrelated to this change;
    // fixing all of them is a separate, unbounded task. `npm run lint`
    // still runs and reports them — this only keeps the build from
    // blocking on lint, matching its behavior before the config existed.
    ignoreDuringBuilds: true,
  },
};

export default config;
