#!/usr/bin/env node
/**
 * "A typed API client generated from or checked against the backend's OpenAPI
 * schema" (§2.1). This is the checked-against half: it reads the live
 * /openapi.json from a running backend and asserts that every enum member and
 * every path the frontend types declare still exists upstream.
 *
 * Run by the `integration` job in ci.yml while the Compose stack is up, so a
 * backend change that would leave the dashboard rendering a blank badge turns
 * the pipeline red rather than reaching a user.
 *
 *   node scripts/check-api-contract.mjs http://localhost:8000
 */
const base = process.argv[2] ?? 'http://localhost:8000'

const EXPECTED_ENUMS = {
  Category: ['water', 'electricity', 'sanitation', 'roads', 'streetlights', 'other'],
  Priority: ['high', 'normal', 'low'],
  Status: ['open', 'in_progress', 'resolved', 'rejected'],
}

const EXPECTED_PATHS = [
  ['/api/complaints', 'post'],
  ['/api/complaints', 'get'],
  ['/api/complaints/{complaint_id}', 'get'],
  ['/api/complaints/{complaint_id}/status', 'patch'],
  ['/api/stats', 'get'],
  ['/api/meta/providers', 'get'],
  ['/health', 'get'],
  ['/ready', 'get'],
  ['/metrics', 'get'],
]

const failures = []

const res = await fetch(`${base}/openapi.json`)
if (!res.ok) {
  console.error(`could not read ${base}/openapi.json (HTTP ${res.status})`)
  process.exit(1)
}
const schema = await res.json()

for (const [name, members] of Object.entries(EXPECTED_ENUMS)) {
  const upstream = schema.components?.schemas?.[name]?.enum
  if (!Array.isArray(upstream)) {
    failures.push(`enum ${name} is missing from the backend schema`)
    continue
  }
  for (const member of members) {
    if (!upstream.includes(member)) failures.push(`${name}.${member} no longer exists upstream`)
  }
  for (const member of upstream) {
    if (!members.includes(member)) {
      failures.push(`${name}.${member} exists upstream but the frontend does not know it`)
    }
  }
}

for (const [path, method] of EXPECTED_PATHS) {
  if (!schema.paths?.[path]?.[method]) failures.push(`${method.toUpperCase()} ${path} is gone`)
}

if (failures.length > 0) {
  console.error('API contract drift between frontend/src/api/types.ts and the backend:')
  for (const f of failures) console.error(`  - ${f}`)
  process.exit(1)
}

console.log(`API contract OK against ${base} (${EXPECTED_PATHS.length} paths, 3 enums)`)
