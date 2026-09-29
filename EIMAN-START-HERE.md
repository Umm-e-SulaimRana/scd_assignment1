# Your part — B, G, H, I (73 marks). What's here and what to do with it.

Everything in this zip is your half: frontend, Docker, Kubernetes, CI/CD.
Sulaim's `backend/` is untouched — none of these files overwrite anything of
hers except `docker-compose.dev.yml`, which is superseded (see step 2).

It is all real, working code, not scaffolding. The frontend builds, its 16
tests pass, both Kustomize overlays render and validate against real
Kubernetes 1.30 schemas, and all three workflows pass `actionlint`. Verified
output at the end of this file.

---

## 1. What's in the zip

| Path | Rubric part | Marks |
|---|---|---|
| `frontend/` | **B** · Frontend | 18 |
| `compose.yaml`, `compose.prod.yaml`, `frontend/Dockerfile`, `frontend/.dockerignore`, `.env.example`, `.gitignore` | **G** · Docker & Compose | 15 |
| `k8s/base/`, `k8s/overlays/{dev,prod}/` | **H** · Kubernetes | 20 |
| `.github/workflows/{ci,cd,release}.yml` | **I** · CI/CD | 20 |
| `docs/adr/0002`, `docs/adr/0003`, `docs/RUNBOOK.md`, `README.md` | **J** (shared) | — |
| `scripts/` | evidence capture for G and H | — |

## 2. Getting it into the repo

Unzip it over your clone. Then delete Sulaim's dev compose file — `compose.yaml`
replaces it and has her exact service names, network names and volume names,
so nothing of hers breaks:

```bash
cd civicpulse                 # your team's repo
unzip ~/Downloads/eiman-parts.zip -d .
git rm docker-compose.dev.yml
```

Two find-and-replaces before you commit:

```bash
# 1. Umm-e-SulaimRana/scd_assignment1 -> your real GitHub org/repo, everywhere
grep -rl 'Umm-e-SulaimRana/scd_assignment1' . --exclude-dir=node_modules --exclude-dir=.git \
  | xargs sed -i '' 's|Umm-e-SulaimRana/scd_assignment1|your-org/civicpulse|g'      # macOS sed needs the ''

# 2. Same in the README badges.
```

Then check it runs before you commit anything:

```bash
cp .env.example .env
docker compose up -d --build
until curl -fsS http://localhost:8000/ready; do sleep 2; done
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed
open http://localhost:8080
```

**Before your first commit**, confirm `.env` is ignored. A key anywhere in git
history is −20 marks *and* a forced credential rotation:

```bash
git status --short | grep -c '\.env$'    # must print 0
git check-ignore -v .env                 # must name .gitignore
```

## 3. Commit it as several PRs, not one

Rubric A wants ≥ 5 merged PRs each linked to an Issue with a substantive
review comment from Sulaim, ≥ 35 commits with conventional prefixes, and
neither partner below 35% by `git shortlog -sn`. One giant commit throws
those marks away. Split it roughly like this, each from `dev` into a feature
branch and back by PR:

| Branch | Contents | Suggested commits |
|---|---|---|
| `feat/frontend-scaffold` | `frontend/` config, `src/api/`, `src/config.ts` | 4–5 |
| `feat/frontend-views` | the three views, badges, error boundary, styles | 5–6 |
| `test/frontend-components` | `src/test/` | 3 |
| `feat/docker-compose` | `frontend/Dockerfile`, both compose files, `.env.example`, `.gitignore`, `scripts/` | 5–6 |
| `feat/k8s-manifests` | `k8s/` | 6–7 |
| `feat/cicd` | `.github/workflows/` | 5–6 |
| `docs/adrs-and-runbook` | `docs/`, `README.md` | 3–4 |

Prefixes: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`.

Also still owed under A, and neither is in this zip because both need your
repository:

- **main protected** — Settings → Branches → add a rule on `main`: require a
  PR, require status checks (`lint-and-type`, `test-backend`, `test-frontend`,
  `build`, `scan`, `manifests`, `integration`), require 1 approval.
  Screenshot it into `docs/evidence/`.
- **One deliberate merge conflict**, resolved, with the markers and 2–4
  sentences on why that version won. Easiest honest one: you and Sulaim both
  edit the same `.env.example` line, or both touch `compose.yaml`'s backend
  environment block.

## 4. What only you can produce

These need your machine or your cluster. Each is worth marks and none of it
can be fabricated.

**Build context and image sizes (G, 2 marks + 4 marks)**

```bash
./scripts/measure-build-context.sh | tee docs/evidence/build-context.txt
./scripts/measure-image-sizes.sh   | tee docs/evidence/image-sizes.txt
```

The frontend image should land near 50 MB. If it is over 60, the multi-stage
split is broken — check nothing copies `node_modules` into the runtime stage.

**Network isolation proof (G, 4 marks)**

```bash
./scripts/prove-isolation.sh | tee docs/evidence/network-isolation.txt
```

Six checks, all must pass. Film the `frontend -> database` failure for the
demo video — a failing command as evidence of correct design is a good thing
to show.

**HPA scale-out (H, 4 marks)**

Needs metrics-server on the cluster and k6 installed (`brew install k6`).

```bash
# terminal 1
./scripts/capture-hpa.sh
# terminal 2
k6 run --out csv=docs/evidence/k6-load.csv scripts/load-test.js
```

You get `hpa-watch.txt` (the raw `kubectl get hpa -w` the rubric names) and
`hpa-series.csv`. Chart replicas against offered load from the CSV, then
write the 3–5 sentences on the lag — the script prints where to read it and
what makes it up.

**VPA recommendation (H, 3 marks)**

```bash
# install the VPA CRDs first (autoscaler repo, hack/vpa-up.sh), then:
kubectl apply -f k8s/base/vpa.yaml
# run the load test, wait ~10 min for it to gather samples, then:
./scripts/capture-vpa.sh | tee docs/evidence/vpa-recommendation.txt
```

Then do the loop the rubric actually asks for: update
`k8s/base/backend.yaml`'s `resources.requests` to the Target it recommends,
commit that, re-run the load test, and write down what changed about HPA
behaviour. (Raising the request lowers computed utilisation for the same real
load, so it crosses 60% later and scales out less. That is the same coupling
that makes `updateMode: Auto` unsafe alongside an HPA — question 6.)

`vpa.yaml` is deliberately **not** in `k8s/base/kustomization.yaml`, because
kubeconform in CI has no schema for a CRD and would fail the build. Apply it
separately.

**Red pipeline blocking a merge, then green (I, 1 mark)**

Open a PR that deliberately breaks one frontend test (change an expected
string). Screenshot the red check and the greyed-out merge button, fix it in
the same PR, screenshot the green. Both into `docs/evidence/`.

**Screenshots for the README** — `submit.png`, `dashboard.png`, `stats.png`,
`hpa-scaleout.png` into `docs/evidence/screenshots/`. The README already
references those exact filenames.

## 5. Repository settings CD needs

Settings → Secrets and variables → Actions:

- `POSTGRES_PASSWORD` — any value; CD creates the cluster Secret from it
- `GROQ_API_KEY` — Sulaim's free Groq key

`GITHUB_TOKEN` is automatic; `cd.yml` scopes it to `packages: write`, which
is the scoped revocable registry token the rubric asks for rather than an
account password.

Settings → Actions → General → Workflow permissions: **Read repository
contents and packages permissions**. Every workflow widens per-job from there.

## 6. Split with Sulaim for the shared parts

`docs/ENGINEERING-NOTES.md` (§5.2, eight questions, 2 marks) is not written —
half of it is hers. The split that matches who wrote what:

| Q | Topic | Who |
|---|---|---|
| 1 | Three things differing between laptop and CI runner, and the exact line freezing each | **you** |
| 2 | Where the pipeline sits on the CI/CD maturity ladder | **you** |
| 3 | The exact line guaranteeing build-once-deploy-many | **you** — it's in ADR 0003, copy the reasoning |
| 4 | What "correct" means for a probabilistic component; keeping CI deterministic | Sulaim |
| 5 | HPA lag, in seconds, from your own run | **you** — from `hpa-series.csv` |
| 6 | Why VPA is in Off mode; the Auto failure mode | **you** — the comment block in `k8s/base/vpa.yaml` is the answer |
| 7 | Where `internal: true` leaves the hosted-LLM call | **you** — ADR 0003 part 2 |
| 8 | The failure that cost you more than an hour | both, honestly |

Generic answers score zero, so every one of these needs a file-and-line
reference into your own repo.

Also still open: `docs/adr/0001-triage-provider-interface.md` (Sulaim's, it's
her interface) and the ≤ 5 minute demo video with both of you speaking —
clean clone → running system → AI triage → fallback → network isolation
failing → HPA scaling → rollback.

## 7. Things in here you will be asked about at viva

The viva is individual, ten minutes, repository open, and it multiplies your
mark. These are the five most likely questions on your files:

**Why is Postgres a StatefulSet and Redis a Deployment?**
`volumeClaimTemplates` gives each ordinal its own PVC bound for the life of
the StatefulSet, and pods get stable names and ordered rollouts. A Deployment
sharing one RWO volume across replicas would have two Postgres processes
writing one data directory. Redis holds rebuildable cache plus a rate-limit
window at one replica, so a Deployment is honest — but it uses `strategy:
Recreate`, because a rolling update would deadlock waiting for a volume the
old pod still holds.

**Why does `/health` not touch the database?**
A failing liveness probe *restarts the pod*; a failing readiness probe only
*removes it from the Service*. If `/health` queried Postgres, a slow database
would restart every backend pod at once — turning a dependency problem into
an outage. `/ready` does check both dependencies, which is correct, because
its consequence is only "stop sending me traffic".

**Why is `resources.requests` mandatory for the HPA?**
The HPA computes utilisation as usage ÷ request. No request, no denominator,
and it sits at `<unknown>/60%` forever.

**Why not `VITE_API_URL`?**
Vite inlines `import.meta.env` at build time, so the URL becomes a literal
inside a hashed asset. You would need one image per environment and CD's
build-once-deploy-many would be a lie. ADR 0002.

**Show me that the frontend cannot reach the database.**
`scripts/prove-isolation.sh`. `frontend` is on `edge`, `database` and `cache`
are on `internal` with `internal: true`, and `backend` is the only service on
both.

---

## Verified before shipping

```
frontend  npx tsc --noEmit                 clean
frontend  npx eslint src --max-warnings 0  clean
frontend  npx vitest run                   5 files, 16 tests, all passing
frontend  npx vite build                   built in 895ms, 157 KB JS (50 KB gzipped)

k8s       kustomize build overlays/dev     15 objects
k8s       kustomize build overlays/prod    15 objects
k8s       kubeconform -strict, k8s 1.30    30 resources valid, 0 invalid, 0 errors

compose   both files parse; every service has a healthcheck;
          compose.prod.yaml has no build:, no bind mount,
          and no published database or cache port

ci/cd     actionlint on all three workflows   clean
          every publishing and deploying job gated by needs:
```

Not verified here, because this sandbox has no Docker daemon or cluster:
the image builds, the Compose stack running end to end, and anything
involving Kubernetes at runtime. Step 2 is where you find out, and it should
take about five minutes.
