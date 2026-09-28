/**
 * The runtime-config rule, as a test. If someone later "simplifies"
 * config.ts by reading import.meta.env, the first case here still passes but
 * the deploy breaks; the second and third are what actually pin the
 * contract with the container entrypoint.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { loadConfig } from '../config'

afterEach(() => {
  delete window.__CIVICPULSE_CONFIG__
})

describe('runtime configuration', () => {
  it('falls back to the same-origin /api path when nothing is injected', () => {
    expect(loadConfig().apiBase).toBe('/api')
  })

  it('uses whatever /config.js injected at container start', () => {
    window.__CIVICPULSE_CONFIG__ = { apiBase: 'https://api.civicpulse.internal/api' }
    expect(loadConfig().apiBase).toBe('https://api.civicpulse.internal/api')
  })

  it('ignores an empty injected value and strips a trailing slash', () => {
    window.__CIVICPULSE_CONFIG__ = { apiBase: '   ' }
    expect(loadConfig().apiBase).toBe('/api')

    window.__CIVICPULSE_CONFIG__ = { apiBase: 'https://example.test/api/' }
    expect(loadConfig().apiBase).toBe('https://example.test/api')
  })
})
