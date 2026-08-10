#!/usr/bin/env node
/**
 * One command to prepare a fresh checkout: `npm run setup`.
 *
 * Performs exactly the steps CONTRIBUTING.md documents as manual — this
 * automates them, it does not replace that doc as the source of truth.
 */

import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const api = path.join(root, "services/api");
const web = path.join(root, "apps/web");

function run(cmd, args, cwd) {
  const result = spawnSync(cmd, args, { cwd, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (spawnSync("uv", ["--version"]).error) {
  console.error(
    "\n  `uv` is not on PATH. Install it first:\n\n" +
      "    curl -LsSf https://astral.sh/uv/install.sh | sh\n\n" +
      "  then re-run `npm run setup`.\n",
  );
  process.exit(1);
}

console.log("\n  Horolog setup\n");

// Safe to run more than once — e.g. after `git pull` picks up a new
// dependency. `uv venv` itself refuses to touch an existing environment.
if (existsSync(path.join(api, ".venv"))) {
  console.log("  api: virtualenv already exists, updating dependencies");
} else {
  console.log("  api: creating virtualenv");
  run("uv", ["venv", "--python", "3.12"], api);
}
run("uv", ["pip", "install", "-e", ".[dev]"], api);

console.log("  web: installing dependencies");
run("npm", ["install"], web);

const envFile = path.join(root, ".env");
if (existsSync(envFile)) {
  console.log("  .env already exists, leaving it alone");
} else {
  console.log("  copying .env.example -> .env");
  copyFileSync(path.join(root, ".env.example"), envFile);
}

console.log("\n  Done. Run `npm run dev` to start Horolog.\n");
