# Engineering notes (§5.2)

Eiman Wasim (24I-3081) · Umme Sulaim (24I-3062)

Answers 1, 2, 3, 5, 6, 7 are Eiman's; 4 is Sulaim's; 8 is both.

---

## 1. Name three things that differ between your laptop and the CI runner, and the exact line that freezes each

**Python version.** The laptop this was developed on runs Python 3.14. CI runs
3.12. This is not cosmetic: `pip install -r requirements-dev.txt` fails outright
on 3.14, because pydantic-core builds through PyO3 and PyO3 0.22.6 refuses any
interpreter newer than 3.13 — `error: the configured Python interpreter version
(3.14) is newer than PyO3's maximum supported version (3.13)`. The backend test
suite therefore cannot run natively on this machine at all; it was run through
`docker run --rm -v "$PWD/backend:/app" python:3.12-slim`.

Frozen by two lines that must agree:

- `.github/workflows/ci.yml` → `python-version: "3.12"` (jobs `lint-and-type`, `test-backend`)
- `backend/Dockerfile` → `FROM python:3.12-slim`

If those drift apart, CI tests one interpreter and production ships another.

**CPU architecture.** The laptop is arm64 (Apple Silicon); the runner is amd64.
This changes measured output, not just speed: `docs/evidence/image-sizes.txt`
records the final frontend image at **86 MB** on arm64, because
`nginx:1.30.5-alpine` is itself ~85 MB on that architecture. The same Dockerfile
lands near 55 MB on amd64. Any size figure quoted without its architecture is
meaningless, which is why the comment block in `frontend/Dockerfile` names the
architecture alongside the number.

Frozen by `runs-on: ubuntu-24.04`, on every job in all three workflows.

**Node version and dependency resolution.** Frozen by `node-version: "22"` in
`ci.yml`, `FROM node:22.9.0-alpine` in `frontend/Dockerfile`, and — the part
that actually matters — `npm ci` rather than `npm install` in the CI jobs. `npm
ci` installs exactly the tree in `package-lock.json` and fails if the lockfile
and `package.json` disagree; `npm install` will happily resolve something newer
and rewrite the lockfile underneath you. The lockfile is the freeze; `npm ci` is
what enforces it.

---

## 2. Where does this pipeline sit on the CI/CD maturity ladder?

**Continuous delivery, not continuous deployment**, and the distinction is
load-bearing.

What is genuinely continuous: every push runs `ci.yml` — lint, type-check, both
test suites, an image build, a vulnerability and misconfiguration scan, manifest
validation against real Kubernetes 1.30 schemas, and an integration job that
brings the whole Compose stack up and exercises it end to end. Every job after
the first is gated with `needs:`, so nothing is published from code known to be
broken and nothing is deployed that was not published. Merging to `main` runs
`cd.yml`, which builds both images once, tags them `${{ github.sha }}`, attaches
SBOMs, and deploys that exact SHA to a cluster.

What is not automated, and is therefore where the ladder stops:

- **No staging environment.** `overlays/dev` and `overlays/prod` exist, but there
  is no long-lived pre-production cluster that a change passes through first.
- **No progressive delivery.** The rollout is `maxUnavailable: 0` with a rolling
  update — safer than a big-bang restart, but it is not a canary. No percentage
  of traffic is sent to the new version and measured before the rest follows.
- **Rollback is a human decision.** `docs/RUNBOOK.md` documents both mechanisms
  and `kubectl rollout undo` takes seconds, but nothing watches error rates and
  triggers it. There is no automated rollback on an SLO breach.
- **Deploy is by SHA tag, not digest.** `cd.yml` already emits each image's
  digest as a job output (`backend-digest`, `frontend-digest`); pinning the
  manifests to those digests rather than to SHA tags is the remaining step, and
  is what would make the artefact identity cryptographic rather than conventional.

So: strong CI, real CD to a cluster, and a human in the loop for anything that
needs judgment. Claiming continuous deployment would require the last three
bullets.

---

## 3. Which exact line guarantees build-once-deploy-many?

`.github/workflows/cd.yml`, in the `deploy-k8s` job:

```
kustomize edit set image \
  "ghcr.io/OWNER/REPO/backend=${{ env.REGISTRY }}/${{ steps.repo.outputs.name }}/backend:${{ github.sha }}" \
  "ghcr.io/OWNER/REPO/frontend=${{ env.REGISTRY }}/${{ steps.repo.outputs.name }}/frontend:${{ github.sha }}"
```

The guarantee is `${{ github.sha }}` appearing in *both* the `build-push` job
(lines that push `.../backend:${{ github.sha }}` and `.../frontend:${{ github.sha }}`)
and here. The same commit hash names the bytes that were built, the bytes that
were scanned, and the bytes the cluster pulls. Nothing is rebuilt between those
steps, so there is no opportunity for them to differ.

Two things defend that line:

- `ci.yml`, job `manifests`, fails the build if a `:latest` reference ever
  reaches the rendered prod overlay.
- `cd.yml` asserts, after applying, that the running Deployment's image string
  contains the commit SHA — so the check survives someone editing the cluster by
  hand.

The frontend has a second, less obvious dependency on this. If the frontend read
its backend URL from `import.meta.env.VITE_API_URL`, Vite would inline that
string into a hashed asset at build time, and you would need one image per
environment — build-once-deploy-many would be a lie regardless of how the tag
was computed. `frontend/src/config.ts` deliberately has no `import.meta.env`
fallback for that reason. See ADR 0002 and ADR 0003.

---

## 4. What does "correct" mean for a probabilistic component, and how do you keep CI deterministic?

*(Sulaim — this one is about the TriageProvider interface and the test strategy
behind it. Worth referencing `backend/app/providers/triage/base.py`, the four
implementations, and the fact that `test-backend` pins
`TRIAGE_PROVIDER=simulated` while the `integration` job pins
`TRIAGE_PROVIDER=rules`, and why those two choices are different.)*

---

## 5. What is the HPA's scale-out lag, in seconds, measured on your own run?

Measured on k3d (k3s v1.35.5) with the built-in metrics-server, backend at
`requests.cpu: 100m`, HPA target 60%, min 1 max 3. Raw data in
`docs/evidence/hpa-watch.txt` and `docs/evidence/hpa-series.csv`; the load is
`scripts/load-test.js` stepping from 5 to 60 virtual users.

| elapsed | event |
|---|---|
| ~60s | load arrives, utilisation 5% -> 45% |
| 78s | 64%, first sample above the 60% target |
| 109s | HPA raises desiredReplicas 1 -> 2 |
| 114s | second pod Ready |
| 140s | desiredReplicas -> 3 |
| 145s | third pod Ready |

**31 seconds from the metric crossing the target to the HPA acting, and 36
seconds to real added capacity.**

The decision is almost all of it. Of that 31s, roughly 15s is metrics-server's
scrape interval and roughly 15s is the HPA controller's sync period, and those
two are serial: the controller can only act on a value that has already been
published. Pod startup contributed 5s -- the container was Ready almost
immediately, because the startup probe passed on its first attempt.

The fourth component, image pull, was **zero here and would not be in
production**. The images were side-loaded onto the node with `k3d image import`
before the run, so the kubelet had them locally. Pulling
`ghcr.io/OWNER/REPO/backend:<sha>` on a cold node would add however long that
takes to every one of these numbers, and it is the component most likely to
dominate on a real cluster.

One result worth not glossing over: at 3 replicas utilisation stayed at
116-122%, well above target, for the whole hold. The HPA was not satisfied, it
was **capped** -- `maxReplicas: 3` in the dev overlay stopped it going further.
The autoscaler behaved correctly; the ceiling was wrong for that load. A number
that says "it scaled out in 36 seconds" without saying it then ran pinned at
its limit would be describing only the half of the run that looks good.

---

## 6. Why is the VPA in `updateMode: "Off"`, and what is the failure mode of `Auto`?

`k8s/base/vpa.yaml` sets `updateMode: "Off"`, which means the VPA observes and
recommends but never evicts a pod to resize it.

The reason is a feedback loop with the HPA, and it is not hypothetical. The HPA
scales on CPU utilisation, which it computes as **usage ÷ request**. The VPA in
`Auto` mode changes the denominator of that fraction. Point them both at CPU and
they fight:

1. VPA raises the CPU request.
2. Computed utilisation falls — same real usage, bigger denominator.
3. The HPA sees headroom and scales **in**.
4. The surviving pods each absorb more load.
5. The VPA observes higher usage and raises the request again.

The loop does not settle in either direction; the cluster oscillates, and each
oscillation costs pod restarts, because `Auto` resizes by evicting. Recommender
mode plus a human reading the numbers and editing `resources.requests` in the
manifest is current industrial practice for exactly this reason.

There is a second, quieter consequence worth stating: `resources.requests` is
mandatory for the HPA to function at all. With no request there is no
denominator and the HPA sits at `<unknown>/60%` forever. So the two controllers
are coupled through a field neither of them owns alone, which is the real
argument against automating both ends of it.

`vpa.yaml` is deliberately excluded from `k8s/base/kustomization.yaml`, because
kubeconform in CI has no schema for a CRD and would fail the build. It is applied
separately.

---

## 7. `internal: true` blocks outbound traffic. Where does that leave the hosted LLM call?

§3.2 requires two networks: `edge` for frontend↔backend, and `internal` for
backend↔database↔cache with `internal: true` set. That flag removes the
network's route to the outside world entirely — which is the point, since the
database and the cache should have no path to the internet in either direction.

But `LLMTriage` calls `https://api.groq.com`. Something has to get out.

The resolution is in `compose.yaml`: **the backend joins both networks and is the
only service that does.**

```
frontend  [edge]                -- internet-facing, no route to data
backend   [edge, internal]      -- the single bridge
database  [internal]            -- no route out
cache     [internal]            -- no route out
```

The Groq call leaves via `edge`, which the backend is on. The database and cache
stay on `internal` and can reach nothing. Nothing had to be relaxed to make the
LLM work.

The consequence worth stating plainly: the backend is now the highest-value
target in the system, because it is the only process holding both a route to the
data and a route out. That is why it runs as a non-root user with
`readOnlyRootFilesystem: true` and `capabilities: drop: [ALL]`.

`scripts/prove-isolation.sh` asserts all six directions and
`docs/evidence/network-isolation.txt` records 6/6 passing. The frontend cannot
even *resolve* the name `database` — Docker's DNS only returns names on networks
you are attached to, so segmentation holds at the DNS layer, not merely at the
firewall.

**The honest gap:** on Kubernetes the equivalent is a NetworkPolicy, since all
pods share a flat network by default. That is not implemented in this submission.
The Compose topology enforces segmentation; the Kubernetes manifests currently
do not. See ADR 0003, part 2.

---

## 8. What failure cost you more than an hour, and what did you learn?

**Eiman.** Two HIGH findings in the Trivy scan job — `msgpack 1.1.2`
(GHSA-6v7p-g79w-8964) and `setuptools 70.3.0` (CVE-2025-47273) — that would not
go away. The obvious fix was to upgrade them in `backend/Dockerfile`, so we did:
pip to 26.2.1 and setuptools to 84.0.0, pinned. The next scan reported the exact
same two versions.

The report itself contained the contradiction. It listed
`usr/local/lib/python3.12/site-packages/setuptools-84.0.0.dist-info` as clean,
*and* a target called `Python` still reporting setuptools 70.3.0. Both could not
describe the same filesystem. Inspecting the built image confirmed only 84.0.0
was on disk.

The source turned out to be `pip/_vendor/vendor.txt` — pip's own manifest of the
libraries it bundles, which lists `msgpack==1.1.2` and `setuptools==70.3.0`
regardless of what is installed. Trivy parses that file as a package list. We had
been upgrading things the scanner was never reading.

The fix was to delete pip and setuptools from the runtime stage entirely. The app
runs uvicorn out of `/opt/venv` and installs nothing at runtime, so both are dead
weight; removing them deletes the reported code rather than explaining it away,
shrinks the image, and leaves a runtime that cannot install anything even if a
process in it is compromised.

Two things learned. First, **a scanner reports what it can parse, not what
exists** — when a finding survives a fix that should have worked, question where
the finding is being read from before applying a second fix. Second, we stopped
using CI as the test loop. Running `trivy fs` and `trivy image` locally before
pushing turned a three-minute round trip per attempt into a thirty-second one,
and it immediately surfaced two further findings CI had never even reached,
because the backend step was failing first and ending the job.

*(Sulaim — add yours.)*
