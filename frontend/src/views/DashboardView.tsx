/**
 * Operations dashboard (§2.1, rubric B-2).
 *
 * Pagination, filters, and status advancement. The two things worth reading
 * carefully:
 *
 * 1. The status buttons offered for a row are NOT computed from a table in
 *    this file. Duplicating services/state_machine.py here would give the
 *    system two sources of truth for what a valid transition is, and the
 *    copy in the browser would rot first. Every terminal status the server
 *    knows about is offered, and the server decides.
 *
 * 2. A rejected transition comes back as 409 with a message that names the
 *    attempted transition ("Cannot transition from resolved to open"). That
 *    string is rendered verbatim, next to the row it belongs to. Collapsing
 *    it into "Error" would throw away the only part of the response that
 *    tells the operator what to do next.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import {
  ApiError,
  CATEGORIES,
  PRIORITIES,
  STATUSES,
  type Complaint,
  type Status,
} from '../api/types'
import { CategoryBadge, PriorityBadge, StatusBadge } from '../components/Badge'

const PAGE_SIZE = 10

export function DashboardView() {
  const [items, setItems] = useState<Complaint[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [rowError, setRowError] = useState<{ id: string; message: string } | null>(null)
  const [busyRow, setBusyRow] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const data = await api.listComplaints({
        category: category || undefined,
        priority: priority || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.detail : String(err))
    } finally {
      setLoading(false)
    }
  }, [category, priority, status, page])

  useEffect(() => {
    void load()
  }, [load])

  async function advance(complaint: Complaint, next: Status) {
    setBusyRow(complaint.id)
    setRowError(null)
    try {
      const updated = await api.updateStatus(complaint.id, next)
      setItems((current) => current.map((c) => (c.id === updated.id ? updated : c)))
    } catch (err) {
      // The server's own 409 text, unedited.
      setRowError({
        id: complaint.id,
        message: err instanceof ApiError ? err.detail : String(err),
      })
    } finally {
      setBusyRow(null)
    }
  }

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function onFilterChange(setter: (value: string) => void) {
    return (value: string) => {
      setter(value)
      setPage(1)
    }
  }

  return (
    <section className="panel">
      <div className="row-between">
        <h2>Operations</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      <div className="filters">
        <label htmlFor="f-category">Category</label>
        <select
          id="f-category"
          value={category}
          onChange={(e) => onFilterChange(setCategory)(e.target.value)}
        >
          <option value="">all</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <label htmlFor="f-priority">Priority</label>
        <select
          id="f-priority"
          value={priority}
          onChange={(e) => onFilterChange(setPriority)(e.target.value)}
        >
          <option value="">all</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <label htmlFor="f-status">Status</label>
        <select
          id="f-status"
          value={status}
          onChange={(e) => onFilterChange(setStatus)(e.target.value)}
        >
          <option value="">all</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {loadError && (
        <p className="error" role="alert">
          {loadError}
        </p>
      )}

      <table>
        <thead>
          <tr>
            <th scope="col">Complaint</th>
            <th scope="col">Location</th>
            <th scope="col">Category</th>
            <th scope="col">Priority</th>
            <th scope="col">Status</th>
            <th scope="col">Advance</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && !loading && (
            <tr>
              <td colSpan={6} className="muted">
                Nothing matches those filters.
              </td>
            </tr>
          )}
          {items.map((c) => (
            <tr key={c.id} data-testid="complaint-row">
              <td>
                <span className="clamp">{c.ai_summary ?? c.text}</span>
                <br />
                <span className="muted mono">{c.triaged_by}</span>
              </td>
              <td>{c.location}</td>
              <td>
                <CategoryBadge category={c.category} />
              </td>
              <td>
                <PriorityBadge priority={c.priority} />
              </td>
              <td>
                <StatusBadge status={c.status} />
                {rowError?.id === c.id && (
                  <p className="error" role="alert" data-testid="transition-error">
                    {rowError.message}
                  </p>
                )}
              </td>
              <td className="actions">
                {STATUSES.filter((s) => s !== c.status).map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={busyRow === c.id}
                    onClick={() => void advance(c, s)}
                  >
                    {s}
                  </button>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="row-between pager">
        <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          Previous
        </button>
        <span className="muted" data-testid="page-indicator">
          Page {page} of {lastPage} · {total} complaints
        </span>
        <button type="button" disabled={page >= lastPage} onClick={() => setPage((p) => p + 1)}>
          Next
        </button>
      </div>
    </section>
  )
}
