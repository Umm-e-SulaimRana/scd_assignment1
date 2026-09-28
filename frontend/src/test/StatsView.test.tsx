import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StatsView } from '../views/StatsView'
import { jsonResponse } from './factories'

const STATS = {
  total: 32,
  by_category: { water: 9, roads: 8, electricity: 6, sanitation: 5, streetlights: 3, other: 1 },
  by_priority: { high: 7, normal: 19, low: 6 },
}

const PROVIDERS = {
  active_provider: 'llm:groq',
  triage_cache_hit_rate: 0.3125,
  recent_outcomes: [{ provider: 'llm:groq', latency_ms: 812, fallback: false, at: 1_759_000_000 }],
}

function stubStats(cache: string) {
  return vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/stats')) {
      return Promise.resolve(jsonResponse(STATS, { headers: { 'X-Cache': cache } }))
    }
    return Promise.resolve(jsonResponse(PROVIDERS))
  })
}

describe('StatsView', () => {
  it('reads the X-Cache header and shows the cache state in the UI', async () => {
    vi.stubGlobal('fetch', stubStats('MISS'))

    render(<StatsView />)
    expect(await screen.findByTestId('cache-badge')).toHaveTextContent('X-Cache: MISS')
    expect(screen.getByTestId('total')).toHaveTextContent('32')
  })

  it('flips to HIT when Redis serves the second request', async () => {
    const fetchSpy = vi
      .fn()
      .mockImplementationOnce(() =>
        Promise.resolve(jsonResponse(STATS, { headers: { 'X-Cache': 'MISS' } })),
      )
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(PROVIDERS)))
      .mockImplementationOnce(() =>
        Promise.resolve(jsonResponse(STATS, { headers: { 'X-Cache': 'HIT' } })),
      )
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(PROVIDERS)))
    vi.stubGlobal('fetch', fetchSpy)
    const user = userEvent.setup()

    render(<StatsView />)
    expect(await screen.findByTestId('cache-badge')).toHaveTextContent('MISS')

    await user.click(screen.getByRole('button', { name: /refresh/i }))
    expect(await screen.findByText(/X-Cache: HIT/)).toBeInTheDocument()
  })

  it('shows the measured triage cache hit rate from /api/meta/providers', async () => {
    vi.stubGlobal('fetch', stubStats('HIT'))

    render(<StatsView />)
    // 0.3125 is a measured rate, not a placeholder: it renders as 31.3%.
    expect(await screen.findByTestId('hit-rate')).toHaveTextContent('31.3%')
  })
})
