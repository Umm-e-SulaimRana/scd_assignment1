# ADR 0003 — Deploy by immutable reference, and where the network split leaves the LLM call

- **Status:** Accepted
- **Date:** 2026-09-27
- **Owner:** Eiman Wasim (24I-3081)
- **Relates to:** §3.2, §3.4 non-negotiables, §5.2 questions 3 and 7, §5.3

This ADR covers two decisions that turn out to be the same decision: what
identifies a running system, and what a running system is allowed to reach.

---

## Part 1 — Deploy by commit SHA, never by a floating tag

### Context

A container tag is a mutable pointer. `ghcr.io/org/repo/backend:latest`
means "whatever was pushed there most recently", which is a different set of
bytes every deploy and possibly a different set of bytes from one `docker
pull` to the next. Kubernetes caches by tag too, so `imagePullPolicy:
IfNotPresent` plus a re-pushed `:latest` gives you a cluster where different
nodes run different code under one tag and nothing in the API tells you.

The operational question this breaks is the one that matters at 3 a.m.:
**what is production running?**

### Decision

`cd.yml` tags every image with `${{ github.sha }}` and the `prod` overlay is
pinned to that SHA at deploy time:

```bash
kustomize edit set image \
  "ghcr.io/Umm-e-SulaimRana/scd_assignment1/backend=ghcr.io/$REPO/backend:$GITHUB_SHA" \
  "ghcr.io/Umm-e-SulaimRana/scd_assignment1/frontend=ghcr.io/$REPO/frontend:$GITHUB_SHA"
```

That `kustomize edit set image` line, plus the `image:` field it writes, is
the exact line guaranteeing build-once-deploy-many (engineering question 3).
Break it and the cluster pulls something other than what CI built, scanned
and tested.

`:latest` is still pushed, for convenience when someone wants to try the app
locally. It is never deployed, and `ci.yml`'s `manifests` job fails the build
if a `:latest` reference ever reaches the rendered prod overlay:

```bash
if grep -E 'image:.*:latest' <<<"$rendered"; then exit 1; fi
```

`cd.yml` also asserts after applying that the running Deployment's image
contains the commit SHA, so the check survives a manual edit.

The `build-push` job additionally emits each image's **digest** as a job
output. A digest (`sha256:...`) is the content hash: it cannot be repointed
at different bytes even by someone with registry write access. Pinning the
manifests to digests rather than SHA tags is the §4 bonus and the natural
next step; the SHA tag is already immutable *by convention in this pipeline*
because nothing ever re-pushes one.

### Consequences

- "What is production running?" is answered by `kubectl get deploy backend -o
  jsonpath='{...image}'`, and the SHA in that string pastes straight into
  `git show`.
- Rollback is a re-deploy of a previous SHA, which is a real artefact that
  still exists in the registry — not a rebuild of old source, which may not
  even build any more.
- `release.yml` adds semver tags by copying the manifest
  (`docker buildx imagetools create`) rather than rebuilding. A rebuild from
  the same source produces different bytes — timestamps, transitively
  resolved dependencies — so a "release" would not be the artefact that was
  tested.
- Cost: image names are unreadable. Accepted; `release.yml` exists to attach
  human-readable names to SHAs worth naming.

---

## Part 2 — `internal: true` blocks outbound traffic. Where does that leave the LLM call?

This is engineering question 7, and it is a real consequence of a decision
made for a different reason.

### Context

§3.2 requires two Docker networks:

```
edge      frontend <-> backend
internal  backend <-> database <-> cache       internal: true
```

`internal: true` removes the network's route to the outside world entirely.
That is the point: the database and the cache are the crown jewels and should
have no path to the internet, inbound or outbound.

But `LLMTriage` calls `https://api.groq.com`. Something has to be able to
reach the internet.

### Decision

**The backend joins both networks and is the only service that does.**

```
frontend  [edge]                       -- internet-facing, no route to data
backend   [edge, internal]             -- the single bridge
database  [internal]                   -- no route out
cache     [internal]                   -- no route out
```

The outbound call to Groq leaves via `edge`, which the backend is on. The
database and cache stay on `internal` and cannot reach anything, which is
exactly the property we wanted. Nothing had to be relaxed.

The `ollama` service is also on `edge`, because it pulls model weights over
HTTPS on first run. Once the weights are in the `ollama_models` volume it
does not need the network again, but the pull has to happen somewhere.

The consequence worth stating plainly: the backend is now the highest-value
target in the system, because it is the only process with both a route to the
data and a route out. That is why it runs as a non-root user with
`readOnlyRootFilesystem: true` and `capabilities: drop: [ALL]`, and why the
`GROQ_API_KEY` is the only credential it holds beyond the database password.

The alternative designs we considered and did not take:

- **A separate `triage-worker` service on `edge` only**, reached by the
  backend over a queue. This is cleaner — the service holding the API key
  would have no database access at all, and a compromise of the LLM
  integration could not read complaints. It is also a queue, a worker, and an
  async write path for a two-person assignment with a four-week clock.
  Correct at scale; over-built here.
- **An egress proxy on `internal`**, allowlisting `api.groq.com`. This keeps
  the backend off `edge` entirely and gives a single auditable egress point,
  which is how a regulated environment would do it. Rejected as a fifth
  container to healthcheck and explain for no marks.

### Verification

`scripts/prove-isolation.sh` asserts all six directions, and `ci.yml`'s
`integration` job asserts the one the rubric names — `frontend -> database`
must fail — so a future change that quietly puts the frontend on `internal`
turns the pipeline red instead of costing 8 marks in marking.

```
frontend -> database   blocked
frontend -> cache      blocked
frontend -> backend    ok
backend  -> database   ok
backend  -> cache      ok
database -> internet   blocked
```

On Kubernetes the equivalent is a NetworkPolicy rather than a network driver
flag, since all pods share a flat network by default. That is not implemented
in this submission and is the honest gap: the Compose topology enforces
segmentation, the Kubernetes manifests currently do not.
