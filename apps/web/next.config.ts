import path from "node:path";
import type { NextConfig } from "next";

const api = process.env.HOROLOG_API_URL ?? "http://localhost:8000";

const config: NextConfig = {
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
};

export default config;
