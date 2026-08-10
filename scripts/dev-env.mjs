/** Environment values that must follow the ports selected by `dev.mjs`.
 *
 * OAuth providers redirect the browser to HOROLOG_PUBLIC_API_URL, and the API
 * redirects back to HOROLOG_PUBLIC_WEB_URL afterwards. Leaving either URL on
 * its default port when the launcher selected a free fallback port strands the
 * OAuth callback in a different (or nonexistent) process.
 */
export function publicRuntimeEnv(env, apiPort, webPort) {
  return {
    ...env,
    HOROLOG_PUBLIC_API_URL:
      env.HOROLOG_PUBLIC_API_URL || `http://localhost:${apiPort}`,
    HOROLOG_PUBLIC_WEB_URL:
      env.HOROLOG_PUBLIC_WEB_URL || `http://localhost:${webPort}`,
  };
}
