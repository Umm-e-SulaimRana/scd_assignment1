# Deliberate merge conflict and its resolution

Two branches changed the same line of `.env.example`.

- `chore/rate-limit-strict` set `RATE_LIMIT_PER_MINUTE=10`, arguing that the
  committed example is the default a fresh clone inherits and should be safe.
- `chore/rate-limit-loadtest` set it to `60`, arguing that `scripts/load-test.js`
  cannot drive the HPA if the limiter sheds the traffic first.

`chore/rate-limit-strict` merged into `dev` first, so merging `dev` back into
`chore/rate-limit-loadtest` produced this conflict:

```
<<<<<<< HEAD
# The k6 load test drives sustained traffic so the HPA has something to scale
# out against. With a low limit the backend answers 429 long before CPU rises,
# and the run measures the rate limiter rather than the autoscaler.
RATE_LIMIT_PER_MINUTE=60
=======
# A citizen reporting a genuine problem does not file ten complaints in a
# minute. Anything above that is a script or a mistake, and the limiter exists
# so the triage provider is not billed for either.
RATE_LIMIT_PER_MINUTE=10
>>>>>>> origin/dev
```

## Resolution, and why

The strict value won. `.env.example` is the file a fresh clone copies to `.env`
and then never looks at again, so whatever sits there becomes the effective
default for everyone who does not think about it. A permissive limit in that
position is a security decision made by omission.

The load-test argument is real but solves the wrong problem in the wrong place.
A benchmark that needs different limits should set them in its own environment
for the duration of the run, not widen the shipped default for every deployment
in order to make one measurement convenient. That keeps the two concerns
separate: the repository ships a safe default, and the load test states its own
requirements where anyone reading the load test can see them.
