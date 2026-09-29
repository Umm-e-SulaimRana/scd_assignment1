# ADR 0002 — The frontend reads its configuration at runtime, not at build time

- **Status:** Accepted
- **Date:** 2026-09-27
- **Owner:** Eiman Wasim (24I-3081)
- **Relates to:** §2.1 "Runtime configuration — the part most students get wrong", §3.1, §5.3

## Context

The frontend has to talk to the backend. The backend lives at a different
address in every environment we run:

| Environment | Where the backend is |
|---|---|
| `npm run dev` on a laptop | `http://localhost:8000` |
| Docker Compose | `http://backend:8000` (service DNS on the `edge` network) |
| Kubernetes | `http://backend.civicpulse.svc.cluster.local:8000` |

The obvious Vite answer is `import.meta.env.VITE_API_URL`. It does not work
here, and the reason is mechanical rather than stylistic: **Vite substitutes
`import.meta.env.*` into the JavaScript at build time.** By the time `vite
build` finishes, the string is a literal inside a hashed, minified asset. It
is not a variable any more; there is nothing left to set.

The consequence is that the image is no longer a build artefact — it is an
environment artefact. You need one image per environment, `docker build` has
to run again to change a URL, and the thing you tested is provably not the
thing you deployed. That is the opposite of build-once-deploy-many, which
CD depends on: `cd.yml` builds each image exactly once, per commit SHA, and
the *same digest* is what the cluster pulls.

A second problem sits behind the first. If the browser calls an absolute
backend URL, that request is cross-origin, so the backend needs permissive
CORS, and a preflight `OPTIONS` precedes every real request.

## Decision

**Two mechanisms, layered. Neither involves rebuilding.**

### 1. Same-origin `/api`, proxied by nginx — the primary mechanism

The app calls `/api/...` on its own origin. `frontend/nginx/default.conf.template`
forwards that prefix to the backend:

```nginx
location /api/ {
    proxy_pass ${BACKEND_ORIGIN};
    ...
}
```

`${BACKEND_ORIGIN}` is substituted by `envsubst` when the container starts —
`nginx:alpine` runs `/docker-entrypoint.d/20-envsubst-on-templates.sh` over
`/etc/nginx/templates/*.template` before starting nginx. Compose sets it to
`http://backend:8000`; the Kubernetes ConfigMap sets it to the cluster DNS
name. On the cluster the Ingress routes `/api` to the backend Service
directly, so the same relative path works there too.

The frontend therefore contains no backend hostname at all. CORS stops being
a problem because there is no cross-origin request to permit, and there is
no preflight on the submit path.

### 2. `/config.js`, generated at container start — the escape hatch

`frontend/docker-entrypoint.d/10-config-js.sh` writes:

```js
window.__CIVICPULSE_CONFIG__ = { apiBase: "/api" };
```

`index.html` loads it with a plain (non-module) `<script>` before the bundle,
so it is guaranteed to have executed by the time React mounts.
`src/config.ts` reads it, falling back to `/api` when it is absent — which is
what happens under `vite dev`, where the dev server proxies `/api` instead.

This exists for the case the proxy cannot cover: a deployment where the API
genuinely is on another origin (a separate api.\* hostname, a CDN in front of
the static assets). Setting `API_BASE=https://api.example.com/api` on the
container repoints the app with a restart and no rebuild.

`src/config.ts` deliberately has **no** `import.meta.env` fallback. Adding one
would let a build-time value creep back in the first time someone is in a
hurry, and it would fail silently: the app would work in dev and point at the
wrong backend in production.

## Consequences

**Good**

- One image, every environment. `cd.yml` builds once and the cluster pulls
  the same digest that CI scanned.
- No CORS and no preflight on the normal path.
- Changing the API address is `kubectl set env` or an edited ConfigMap plus a
  restart, not a pipeline run.
- `/config.js` is served with `Cache-Control: no-store`, so a stale copy can
  never point a browser at a decommissioned backend.

**Costs, accepted**

- One extra network hop through nginx. Negligible against a triage call that
  takes seconds.
- nginx must forward `X-Forwarded-For`, or the backend's Redis rate limiter
  (keyed on client IP) would see the nginx pod's IP and throttle every citizen
  as a single caller. This is set explicitly in the template.
- `readOnlyRootFilesystem: true` on the frontend pod means
  `/usr/share/nginx/html` has to be an `emptyDir` so the entrypoint can write
  `/config.js` into it, which is why `k8s/base/frontend.yaml` has an init
  container that copies the built assets into that volume first.

**Verified by**

- `frontend/src/test/config.test.ts` — the fallback, the injected value, and
  the empty-value case.
- `ci.yml`, job `integration` — fetches `http://localhost:8080/config.js`
  from the running container and asserts the global is present, then calls
  `/api/stats` through the proxy.

## Alternatives rejected

**`VITE_API_URL` at build time.** Rejected above: it destroys
build-once-deploy-many and is the specific trap §2.1 names.

**Fetching `/config.json` with `fetch()` before mounting React.** Works, but
adds a round trip to first paint and a loading state that exists only to
answer a question the server already knew. A synchronous `<script>` costs
nothing measurable.

**Hard-coding relative `/api` with no config hook at all.** Simplest, and it
covers every environment we currently run. Rejected because the escape hatch
is ten lines and the day we need a separate API origin is the day we would
otherwise be rebuilding images under pressure.
