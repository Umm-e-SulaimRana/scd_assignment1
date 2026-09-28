import type { Complaint } from '../api/types'

/** One place that knows the shape of a Complaint, so a schema change breaks one file. */
export function makeComplaint(overrides: Partial<Complaint> = {}): Complaint {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    text: 'Burst water main flooding Street 12 since fajr, water entering ground floors',
    location: 'Sector G-9',
    reporter_contact: null,
    category: 'water',
    priority: 'high',
    status: 'open',
    ai_summary: 'Burst main flooding Street 12; water entering homes.',
    triaged_by: 'llm:groq',
    triage_latency_ms: 812,
    created_at: '2026-09-27T09:00:00Z',
    updated_at: '2026-09-27T09:00:00Z',
    ...overrides,
  }
}

/** A minimal fetch stand-in: body, status, and headers that the client reads. */
export function jsonResponse(
  body: unknown,
  init: { status?: number; headers?: Record<string, string> } = {},
): Response {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
  })
}
