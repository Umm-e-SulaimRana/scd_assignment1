# CivicPulse runbook

What to do when it is running and something is wrong. Written for whoever is
on the other end of the pager, which on this project means whichever of us is
awake.

Contents: [Deploy](#deploy) · [Roll back](#roll-back) · [Read the logs](#read-the-logs) ·
[Triage is failing](#when-triage-starts-failing) · [Other symptoms](#other-symptoms)

---

## Deploy

### Normal path — automatic

Merging a pull request into `main` runs `.github/workflows/cd.yml`:

1. `test` — full suite on the merged result
2. `build-push` — both images to GHCR, tagged `${{ github.sha }}`, SBOMs attached
3. `deploy-k8s` — `kustomize edit set image` to that SHA, apply, wait on
   rollout, smoke-test through the Ingress

Every job after the first has `needs:` on the one before it. Nothing is
published from code known to be broken, and nothing is deployed that was not
published.

### Manual path — deploying a specific SHA

```bash
SHA=<the 40-char commit sha>
REPO=$(echo "$GITHUB_REPOSITORY" | tr '[:upper:]' '[:lower:]')

cd k8s/overlays/prod
kustomize edit set image \
  "ghcr.io/Umm-e-SulaimRana/scd_assignment1/backend=ghcr.io/$REPO/backend:$SHA" \
  "ghcr.io/Umm-e-SulaimRana/scd_assignment1/frontend=ghcr.io/$REPO/frontend:$SHA"
cd -

kustomize build k8s/overlays/prod | kubectl apply -f -
kubectl -n civicpulse rollout status deployment/backend --timeout=300s
```

Never deploy `:latest`. It may be pushed; it may never be deployed. "What is
production running?" has to have an answer you can paste into `git show`.

### Migrations

The app never runs DDL at startup (§2.3). After a deploy that includes a new
migration:

```bash
pod=$(kubectl -n civicpulse get pod -l app.kubernetes.io/name=backend -o name | head -1)
kubectl -n civicpulse exec "$pod" -- alembic upgrade head
kubectl -n civicpulse exec "$pod" -- alembic current
```

If a migration is not backwards-compatible with the currently-running image,
apply it *before* the rollout, not after — `maxUnavailable: 0` means old and
new pods serve simultaneously during a rollout.

---

## Roll back

Two mechanisms. Use the first when the site is down, the second afterwards.

### 1. Imperative — the 3 a.m. answer

```bash
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend --timeout=120s
```

Seconds, one command, no repository access, no CI wait. Use it when the
bleeding needs to stop.

Its weakness: the cluster is now running something the repository does not
describe. Anyone reading `k8s/overlays/prod` is reading a lie, and the next
`kubectl apply` — including one from a later CD run — silently re-applies the
broken version.

Inspect history with:

```bash
kubectl -n civicpulse rollout history deployment/backend
kubectl -n civicpulse rollout history deployment/backend --revision=3
```

### 2. Declarative — the correct answer once the fire is out

Re-apply the overlay pinned to the previous good SHA:

```bash
PREV=$(git rev-parse HEAD~1)      # or whichever SHA was known good
cd k8s/overlays/prod
kustomize edit set image \
  "ghcr.io/Umm-e-SulaimRana/scd_assignment1/backend=ghcr.io/$REPO/backend:$PREV" \
  "ghcr.io/Umm-e-SulaimRana/scd_assignment1/frontend=ghcr.io/$REPO/frontend:$PREV"
cd -
kustomize build k8s/overlays/prod | kubectl apply -f -
git commit -am "revert: pin prod to $PREV after incident" && git push
```

Slower, but the repository and the cluster agree again, the change is
reviewable, and the next CD run will not undo it.

**Rule of thumb:** `rollout undo` first if users are affected, then
immediately follow with the declarative revert. Never leave the cluster and
the repository disagreeing overnight.

### Rolling back a migration

```bash
kubectl -n civicpulse exec "$pod" -- alembic downgrade -1
```

Check the migration's `downgrade()` body first. A migration that dropped a
column cannot restore its data — in that case restore from a backup instead
of downgrading.

---

## Read the logs

Every line is JSON on stdout, carrying a `request_id` propagated from the
`X-Request-ID` header (generated if the caller did not send one).

```bash
# Follow everything from the backend
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend -f --tail=100

# Just the warnings and errors
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --tail=500 \
  | jq -c 'select(.level == "WARNING" or .level == "ERROR")'

# Everything that happened during one request
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --tail=2000 \
  | jq -c 'select(.request_id == "7f3a...")'

# The previous container, after a crash-restart
kubectl -n civicpulse logs <pod> --previous
```

Under Compose: `docker compose logs -f backend`.

A user reporting a problem should be asked for the request ID if the UI
showed one; otherwise correlate by timestamp and complaint ID.

---

## When triage starts failing

**Symptom:** complaints still return 201, but `triaged_by` is
`rules:fallback` on everything, and categories look crude.

That is the system working as designed — a citizen never sees a 500 because
a third party was rate-limited — but it means the LLM path is broken and
classification quality has dropped. Work through this in order.

### 1. Confirm it, and measure how bad

```bash
curl -s http://civicpulse.local/api/meta/providers | jq
```

Look at `active_provider` and `recent_outcomes`. Count `fallback: true` in
the last twenty. One or two is normal; twenty is an outage.

### 2. Find the error class

```bash
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --tail=500 \
  | jq -c 'select(.event == "triage_fallback")'
```

Each fallback logs one WARNING with the complaint id, the provider and the
error class. That class is the diagnosis:

| Error class | Cause | Action |
|---|---|---|
| `TimeoutError` | Provider slower than the 10s cap | Usually transient. If sustained, switch to `ollama` or `rules` (step 3). |
| `HTTPStatusError` 429 | Free-tier rate limit exhausted | Check the provider's dashboard. Lower `RATE_LIMIT_PER_MINUTE` to shed load, or switch provider. |
| `HTTPStatusError` 401/403 | Key revoked, expired, or wrong | Rotate the Secret (step 4). |
| `ValidationError` | Model returned something that is not a valid `TriageResult` | Model or prompt changed. Pin `GROQ_MODEL` to a known-good version. |
| `ConnectError` | No route out | Check ADR 0003 part 2 — is the backend still on the `edge` network / has egress changed? |

### 3. Switch provider without a rebuild

`TRIAGE_PROVIDER` is read from the ConfigMap at startup, so this is an edit
and a restart, not a pipeline run:

```bash
kubectl -n civicpulse patch configmap civicpulse-config \
  --type merge -p '{"data":{"TRIAGE_PROVIDER":"rules"}}'
kubectl -n civicpulse rollout restart deployment/backend
```

`rules` is deterministic, local, and always available — worse at
classification but never down. `ollama` is the offline model path, if an
Ollama service is running. Switch back the same way.

### 4. Rotate the API key

```bash
kubectl -n civicpulse create secret generic civicpulse-secrets \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=GROQ_API_KEY="$NEW_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n civicpulse rollout restart deployment/backend
```

Also update the `GROQ_API_KEY` GitHub Secret, or the next CD run will write
the old one back.

If the key leaked into git history: revoke it at the provider first, then
rotate, then write the incident note. Revoking comes first because the
rotation takes minutes and the leaked key works until it is revoked.

### 5. Cache hit rate collapsed

`triage_cache_hit_rate` near zero with normal traffic means the content-hash
cache is not being read — usually Redis is unreachable and every call is
going to the provider. Check `/ready`: it returns 503 naming `redis` if so.
This is a cost problem before it is a latency problem; the free tier will be
exhausted quickly.

---

## Other symptoms

### Pods restarting in a loop

```bash
kubectl -n civicpulse get pods
kubectl -n civicpulse describe pod <pod> | sed -n '/Events/,$p'
kubectl -n civicpulse logs <pod> --previous
```

- `CrashLoopBackOff` with `Liveness probe failed` early in the pod's life →
  the process is slow to start, not broken. `startupProbe` should be
  absorbing this; if it is not, raise `failureThreshold`.
- `OOMKilled` in the events → the memory limit is too low. Check what VPA
  recommends (`kubectl -n civicpulse describe vpa backend-vpa`) before
  guessing a new number.
- Liveness failing but `/health` returns 200 by hand → the probe is pointed
  somewhere wrong, or the pod is out of file descriptors.

Remember the split: liveness restarts the pod, readiness only removes it from
the Service. If `/health` ever starts touching the database, a slow database
becomes a cluster-wide restart loop.

### `/ready` returns 503

The body names the failed dependency:

```bash
curl -s http://civicpulse.local/ready | jq
# {"status":"not ready","failed":["postgres"]}
```

Pods in this state are out of the Service and will rejoin automatically once
the dependency recovers. Do not restart them — that loses the useful signal
and fixes nothing.

### HPA stuck at `<unknown>/60%`

```bash
kubectl -n civicpulse get hpa
kubectl top pods -n civicpulse
```

Almost always one of two things: metrics-server is not installed or not
ready, or a container is missing `resources.requests.cpu`. The HPA computes
utilisation as usage ÷ request; with no request there is no denominator.

### Everything is slow and replicas are not rising

Check the lag, not just the current state:

```bash
kubectl -n civicpulse get hpa backend -w
```

Scale-out is not instant: metrics-server scrapes on an interval, the HPA
syncs on an interval, then an image has to be pulled and a startup probe has
to pass. Measured lag for this deployment is in
`docs/evidence/hpa-scaleout.txt`. If load arrives faster than that,
autoscaling is not the answer — capacity planning is.

### Rate limiting the wrong people

If every citizen shares one rate-limit bucket, `X-Forwarded-For` is not
reaching the backend and the limiter is keying on the proxy's IP. Check that
the nginx template still sets it (`frontend/nginx/default.conf.template`) and
that the Ingress is not stripping it.

### Data is gone after a restart

It should not be. Verify the claim is still bound:

```bash
kubectl -n civicpulse get pvc
kubectl -n civicpulse get pv
```

`kubectl delete pod postgres-0` re-binds the same PVC and preserves every
row — that is the persistence contract, and the demo. What does destroy data
is `kubectl delete pvc`, or `docker compose down -v`. The `-v` is the
difference.
