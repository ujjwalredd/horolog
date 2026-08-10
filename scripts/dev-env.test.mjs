import assert from "node:assert/strict";
import test from "node:test";

import { publicRuntimeEnv } from "./dev-env.mjs";

test("OAuth URLs follow fallback development ports", () => {
  const env = publicRuntimeEnv({}, 8001, 3001);
  assert.equal(env.HOROLOG_PUBLIC_API_URL, "http://localhost:8001");
  assert.equal(env.HOROLOG_PUBLIC_WEB_URL, "http://localhost:3001");
});

test("explicit public OAuth URLs are preserved", () => {
  const env = publicRuntimeEnv(
    {
      HOROLOG_PUBLIC_API_URL: "https://api.example.test",
      HOROLOG_PUBLIC_WEB_URL: "https://app.example.test",
    },
    8001,
    3001,
  );
  assert.equal(env.HOROLOG_PUBLIC_API_URL, "https://api.example.test");
  assert.equal(env.HOROLOG_PUBLIC_WEB_URL, "https://app.example.test");
});
