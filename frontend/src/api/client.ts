/**
 * The only place in the frontend that knows fetch() exists.
 *
 * Responsibilities: build the URL from runtime config, set headers, and turn
 * every failure -- HTTP status, malformed body, network drop -- into an
 * ApiError carrying the server's own message. Components render errors; they
 * never inspect status codes or parse bodies.
 *
 * What is deliberately NOT here: any business rule. No list of valid status
 * transitions, no category-to-priority mapping, no "high priority means
 * water". Those live in the backend (services/state_machine.py,
 * providers/triage/rules.py) and arrive over the wire. §2.1: the frontend
 * owns presentation and interaction, and owns no business rules.
 */
import { config } from '../config'
import {
  ApiError,
  type Complaint,
  type ComplaintCreate,
  type ComplaintList,
  type ProviderInfo,
  type Stats,
  type StatsResponse,
  type Status,
  type FieldError,
} from './types'

export interface ListParams {
  category?: string
  priority?: string
  status?: string
  page?: number
  page_size?: number
}

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const url = `${config.apiBase}${path}`
  if (!params) return url
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `${url}?${qs}` : url
}

async function toApiError(response: Response): Promise<ApiError> {
  const retryAfterHeader = response.headers.get('Retry-After')
  const retryAfter = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : null

  let detail = `Request failed with status ${response.status}`
  let fieldErrors: FieldError[] = []

  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object') {
      const record = body as Record<string, unknown>
      if (typeof record.detail === 'string') detail = record.detail
      if (Array.isArray(record.errors)) fieldErrors = record.errors as FieldError[]
    }
  } catch {
    // A proxy timeout or an nginx error page is not JSON. Keep the generic
    // message rather than crashing on the parse.
  }

  return new ApiError(response.status, detail, fieldErrors, Number.isNaN(retryAfter) ? null : retryAfter)
}

async function request<T>(path: string, init?: RequestInit, params?: ListParams): Promise<T> {
  let response: Response
  try {
    response = await fetch(buildUrl(path, params as Record<string, string | number | undefined>), {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    // DNS failure, backend down, connection reset. There is no status code.
    throw new ApiError(0, 'Could not reach the CivicPulse API. Is the backend running?', [], null)
  }

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  createComplaint(payload: ComplaintCreate): Promise<Complaint> {
    return request<Complaint>('/complaints', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getComplaint(id: string): Promise<Complaint> {
    return request<Complaint>(`/complaints/${id}`)
  },

  listComplaints(params: ListParams = {}): Promise<ComplaintList> {
    return request<ComplaintList>('/complaints', undefined, params)
  },

  updateStatus(id: string, status: Status): Promise<Complaint> {
    return request<Complaint>(`/complaints/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },

  /**
   * Stats needs the response headers, not just the body: X-Cache tells the
   * operator whether Redis served this or Postgres did. §2.1 asks for it in
   * the UI, so the client surfaces it rather than discarding it.
   */
  async getStats(): Promise<StatsResponse> {
    let response: Response
    try {
      response = await fetch(buildUrl('/stats'))
    } catch {
      throw new ApiError(0, 'Could not reach the CivicPulse API. Is the backend running?')
    }
    if (!response.ok) throw await toApiError(response)

    const header = response.headers.get('X-Cache')
    const cache: StatsResponse['cache'] =
      header === 'HIT' || header === 'MISS' ? header : 'UNKNOWN'
    return { stats: (await response.json()) as Stats, cache }
  },

  getProviders(): Promise<ProviderInfo> {
    return request<ProviderInfo>('/meta/providers')
  },
}
