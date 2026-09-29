/**
 * Stats view (§2.1, rubric B-3).
 *
 * Aggregate counts by category and priority, plus the thing that makes this
 * view worth building: the X-Cache header is shown in the interface. Hit
 * "Refresh" twice inside the 30 second TTL and it flips MISS -> HIT in front
 * of you; submit a complaint and it flips back, because complaint_service.py
 * deletes the key on write instead of waiting for the TTL to lapse.
 *
 * /api/meta/providers is rendered underneath for the same reason: which
 * provider is live, the measured triage cache hit rate, and the last twenty
 * outcomes with their latencies and whether each fell back.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { ApiError, type ProviderInfo, type StatsResponse } from '../api/types'
import { CacheBadge } from '../components/Badge'

function Bars({ data, total }: { data: Record<string, number | undefined>; total: number }) {
  const entries = Object.entries(data).filter(([, n]) => typeof n === 'number') as [string, number][]
  if (entries.length === 0) return <p className="muted">No data yet.</p>
  return (
    <ul className="bars">
      {entries
        .sort((a, b) => b[1] - a[1])
        .map(([key, count]) => (
          <li key={key}>
            <span className="bar-label">{key}</span>
            <span
              className="bar"
              style={{ width: `${total > 0 ? Math.round((count / total) * 100) : 0}%` }}
              aria-hidden="true"
            />
            <span className="bar-count">{count}</span>
          </li>
        ))}
    </ul>
  )
}

export function StatsView() {
  const [data, setData] = useState<StatsResponse | null>(null)
  const [providers, setProviders] = useState<ProviderInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [stats, meta] = await Promise.all([api.getStats(), api.getProviders()])
      setData(stats)
      setProviders(meta)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="panel">
      <div className="row-between">
        <h2>Statistics</h2>
        <div className="row-gap">
          {data && <CacheBadge cache={data.cache} />}
          <button type="button" onClick={() => void load()} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {data && (
        <>
          <p data-testid="total">
            <strong>{data.stats.total}</strong> complaints on record.
          </p>
          <p className="muted">
            {data.cache === 'HIT'
              ? 'Redis served this response. Refresh again after 30 seconds, or submit a complaint, and it will say MISS.'
              : 'Postgres served this response and Redis has now cached it for 30 seconds.'}
          </p>

          <h3>By category</h3>
          <Bars data={data.stats.by_category} total={data.stats.total} />

          <h3>By priority</h3>
          <Bars data={data.stats.by_priority} total={data.stats.total} />
        </>
      )}

      {providers && (
        <div className="panel panel-inset">
          <h3>Triage layer</h3>
          <p>
            Active provider <span className="mono">{providers.active_provider}</span> · measured
            cache hit rate{' '}
            <span className="mono" data-testid="hit-rate">
              {(providers.triage_cache_hit_rate * 100).toFixed(1)}%
            </span>
          </p>
          {providers.recent_outcomes.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th scope="col">Provider</th>
                  <th scope="col">Latency</th>
                  <th scope="col">Fell back?</th>
                </tr>
              </thead>
              <tbody>
                {providers.recent_outcomes.map((o, i) => (
                  <tr key={i}>
                    <td className="mono">{o.provider}</td>
                    <td>{o.latency_ms} ms</td>
                    <td>{o.fallback ? 'yes' : 'no'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  )
}
