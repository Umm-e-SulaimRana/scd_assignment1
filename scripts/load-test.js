// k6 load profile for the HPA scale-out evidence (§3.3 deliverable).
//
//   k6 run --out csv=docs/evidence/k6-load.csv scripts/load-test.js
//
// The shape matters more than the numbers. A flat load never shows the lag
// that the deliverable is asking about; a step up does. The ramp holds long
// enough for metrics-server to publish a new average (it scrapes every 15s
// by default) and for the HPA controller to act on it (every 15s), which is
// most of the lag you will measure.
//
// GET /api/stats is the right target: it is cheap enough that the load
// generator is not the bottleneck, and it exercises the Redis read-through
// path rather than burning free LLM quota on every request.
import http from 'k6/http'
import { check, sleep } from 'k6'

const BASE = __ENV.BASE_URL || 'http://civicpulse.local'

export const options = {
  stages: [
    { duration: '30s', target: 5 },    // warm-up: pools open, JIT settles
    { duration: '30s', target: 5 },    // baseline -- note the replica count here
    { duration: '10s', target: 60 },   // the step. t=70s is your "load arrived" mark
    { duration: '3m', target: 60 },    // hold: watch replicas climb and latency recover
    { duration: '30s', target: 5 },    // drop, to observe the 300s scale-down window
    { duration: '2m', target: 5 },
  ],
  thresholds: {
    // Deliberately generous: this run is measuring autoscaler behaviour, not
    // asserting an SLO. A failed threshold here would hide the actual result.
    http_req_failed: ['rate<0.05'],
  },
}

export default function () {
  const res = http.get(`${BASE}/api/stats`)
  check(res, {
    'status is 200': (r) => r.status === 200,
    'X-Cache present': (r) => r.headers['X-Cache'] !== undefined,
  })
  sleep(0.2)
}
