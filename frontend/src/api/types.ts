/**
 * Typed mirror of the backend's OpenAPI schema (backend/app/schemas.py).
 *
 * These are checked against the live schema in CI, not maintained by hand and
 * hoped about: `npm run check:api` fetches /openapi.json from a running
 * backend and asserts that every enum member below still exists upstream
 * (scripts/check-api-contract.mjs). If Sulaim adds a category, the check goes
 * red before a user ever sees a blank badge.
 */

export const CATEGORIES = [
  'water',
  'electricity',
  'sanitation',
  'roads',
  'streetlights',
  'other',
] as const
export type Category = (typeof CATEGORIES)[number]

export const PRIORITIES = ['high', 'normal', 'low'] as const
export type Priority = (typeof PRIORITIES)[number]

export const STATUSES = ['open', 'in_progress', 'resolved', 'rejected'] as const
export type Status = (typeof STATUSES)[number]

export interface Complaint {
  id: string
  text: string
  location: string
  reporter_contact: string | null
  category: Category
  priority: Priority
  status: Status
  ai_summary: string | null
  triaged_by: string
  triage_latency_ms: number
  created_at: string
  updated_at: string
}

export interface ComplaintList {
  items: Complaint[]
  total: number
  page: number
  page_size: number
}

export interface ComplaintCreate {
  text: string
  location: string
  reporter_contact?: string | null
}

export interface Stats {
  total: number
  by_category: Partial<Record<Category, number>>
  by_priority: Partial<Record<Priority, number>>
}

export interface TriageOutcome {
  provider: string
  latency_ms: number
  fallback: boolean
  at: number
}

export interface ProviderInfo {
  active_provider: string
  triage_cache_hit_rate: number
  recent_outcomes: TriageOutcome[]
}

/** What GET /api/stats returned, plus whether Redis served it (X-Cache header). */
export interface StatsResponse {
  stats: Stats
  cache: 'HIT' | 'MISS' | 'UNKNOWN'
}

/** FastAPI's field-level 400 body (main.py validation_exception_handler). */
export interface FieldError {
  loc: (string | number)[]
  msg: string
  type: string
}

/**
 * Every non-2xx from the API arrives as one of these. `detail` is the server's
 * own message and is rendered verbatim -- the 409 from PATCH
 * /api/complaints/{id}/status names the exact attempted transition, and
 * replacing that with "Something went wrong" throws away the only useful
 * information in the response.
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly fieldErrors: FieldError[]
  readonly retryAfter: number | null

  constructor(
    status: number,
    detail: string,
    fieldErrors: FieldError[] = [],
    retryAfter: number | null = null,
  ) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.fieldErrors = fieldErrors
    this.retryAfter = retryAfter
  }
}
