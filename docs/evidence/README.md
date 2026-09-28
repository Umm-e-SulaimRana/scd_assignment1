# Evidence

Nothing in this folder can be generated in advance — every file is the output
of a command run against a real stack or a real cluster. `scripts/` produces
most of it.

| File | Produced by | Rubric |
|---|---|---|
| `build-context.txt` | `./scripts/measure-build-context.sh` | G · .dockerignore, before/after sizes |
| `image-sizes.txt` | `./scripts/measure-image-sizes.sh` | G · both stage sizes, non-root proof |
| `network-isolation.txt` | `./scripts/prove-isolation.sh` | G · frontend provably cannot reach the database |
| `hpa-watch.txt`, `hpa-series.csv` | `./scripts/capture-hpa.sh` + `k6 run scripts/load-test.js` | H · captured `kubectl get hpa -w`, replicas-vs-load chart |
| `vpa-recommendation.txt` | `./scripts/capture-vpa.sh` | H · Target / Lower Bound / Upper Bound |
| `branch-protection.png` | screenshot of Settings → Branches | A · main protected, checks required, 1 approval |
| `pipeline-red.png`, `pipeline-green.png` | screenshot of a PR with a deliberately failing test, then fixed | I · a red pipeline blocking a merge |
| `screenshots/submit.png` | the running app | J · README |
| `screenshots/dashboard.png` | the running app | J · README |
| `screenshots/stats.png` | the running app, showing `X-Cache` | J · README |
| `screenshots/hpa-scaleout.png` | chart from `hpa-series.csv` | H, J |
