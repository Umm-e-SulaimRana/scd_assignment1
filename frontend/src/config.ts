/**
 * Runtime configuration.
 *
 * The rule this file exists to enforce: nothing about the environment is
 * known at build time. `vite build` runs once, in CI, and the resulting
 * image is the same bytes in dev, in Compose and on the cluster.
 *
 * Resolution order:
 *   1. window.__CIVICPULSE_CONFIG__ -- written by /config.js, which the
 *      container entrypoint generates from environment variables at start.
 *   2. "/api" -- same-origin relative path. nginx proxies it to the backend
 *      (frontend/nginx/default.conf.template), so the browser never needs to
 *      know a backend hostname and there is no CORS preflight at all.
 *
 * There is deliberately no import.meta.env fallback: adding one would let a
 * build-time value creep back in the first time someone is in a hurry.
 */

export interface RuntimeConfig {
  apiBase: string
}

declare global {
  interface Window {
    __CIVICPULSE_CONFIG__?: Partial<RuntimeConfig>
  }
}

const DEFAULT_API_BASE = '/api'

export function loadConfig(): RuntimeConfig {
  const injected = typeof window !== 'undefined' ? window.__CIVICPULSE_CONFIG__ : undefined
  const apiBase = injected?.apiBase?.trim()
  return { apiBase: apiBase && apiBase.length > 0 ? apiBase.replace(/\/$/, '') : DEFAULT_API_BASE }
}

export const config = loadConfig()
