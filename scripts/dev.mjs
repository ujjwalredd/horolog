#!/usr/bin/env node
/**
 * One command to run Horolog locally: `npm run dev`.
 *
 * Starts the API and the web app together, on ports that are actually free.
 * Two things this exists to prevent, both of which cost real debugging time:
 *
 *   1. Two `next dev` processes sharing one `.next` directory. They overwrite
 *      each other's chunks and the second one fails with a baffling
 *      "Cannot find module './833.js'". A stale `.next` from a production
 *      `next build` does the same, so it is cleared on start.
 *   2. Hard-coded ports. If 8000 is taken by something else, the web app
 *      proxies to a stranger and every request 500s with no obvious cause.
 */

import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const api = path.join(root, "services/api");
const web = path.join(root, "apps/web");

function free(port) {
  return new Promise((resolve) => {
    const probe = createServer()
      .once("error", () => resolve(false))
      .once("listening", () => probe.close(() => resolve(true)))
      .listen(port, "127.0.0.1");
  });
}

async function pick(preferred, label) {
  for (let port = preferred; port < preferred + 40; port++) {
    if (await free(port)) {
      if (port !== preferred) {
        console.log(`  ${label}: ${preferred} is in use, using ${port}`);
      }
      return port;
    }
  }
  throw new Error(`no free port for ${label} near ${preferred}`);
}

const venv = path.join(api, ".venv/bin/python");
if (!existsSync(venv)) {
  console.error(
    "\n  The API virtualenv is missing. Create it first:\n\n" +
      "    cd services/api\n" +
      "    uv venv --python 3.12 && uv pip install -e '.[dev]'\n",
  );
  process.exit(1);
}

// A `.next` left behind by `next build` is not a valid dev cache.
rmSync(path.join(web, ".next"), { recursive: true, force: true });

const apiPort = await pick(Number(process.env.HOROLOG_PORT) || 8000, "api");
const webPort = await pick(Number(process.env.PORT) || 3000, "web");

console.log(`\n  Horolog\n  api  http://localhost:${apiPort}\n  web  http://localhost:${webPort}\n`);

const children = [
  spawn(venv, ["-m", "uvicorn", "horolog.api:app", "--reload", "--port", String(apiPort)], {
    cwd: api,
    stdio: "inherit",
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  }),
  spawn("npx", ["next", "dev", "-p", String(webPort)], {
    cwd: web,
    stdio: "inherit",
    env: { ...process.env, HOROLOG_API_URL: `http://localhost:${apiPort}` },
  }),
];

let closing = false;
function shutdown() {
  if (closing) return;
  closing = true;
  for (const child of children) child.kill("SIGTERM");
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
// If either half dies, take the other with it — a web server proxying to a
// dead API is worse than no server at all, because it looks like it works.
for (const child of children) child.on("exit", shutdown);
