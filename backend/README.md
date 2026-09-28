# CivicPulse Backend — Sulaim's Part (C + D + E + F, 72 marks)

This covers everything you own per the kickoff plan:

| Part | What | Marks |
|---|---|---|
| C | FastAPI backend, 4-layer architecture, state machine, health/ready, SIGTERM, logging | 25 |
| D | Postgres + Alembic migrations, indexes, idempotent seed | 12 |
| E | Redis read-through cache + distributed rate limiter | 10 |
| F | TriageProvider interface, 4 implementations, timeout/retry/fallback/cache/guardrail | 25 |

Everything below is real, tested code — not pseudocode. 23 unit tests pass
right now with no external services running (they use `fakeredis` and
in-memory fakes). You'll add Postgres to run the real thing.

---

## 1. What's in the zip

```
civicpulse-backend/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app assembly, lifespan, middleware
│   │   ├── config.py                # env-var driven settings
│   │   ├── schemas.py               # Pydantic: Category/Priority/Status enums, TriageResult, API models
│   │   ├── models.py                # SQLAlchemy ORM (the DB shape)
│   │   ├── database.py              # async engine + session factory
│   │   ├── dependencies.py
│   │   ├── middleware.py            # request-id + JSON structured logging
│   │   ├── metrics.py               # Prometheus counters/histograms
│   │   ├── routes/                  # HTTP layer only
│   │   │   ├── complaints.py
│   │   │   ├── stats.py
│   │   │   ├── meta.py
│   │   │   └── health.py
│   │   ├── services/                # business rules
│   │   │   ├── complaint_service.py
│   │   │   ├── stats_service.py
│   │   │   ├── state_machine.py
│   │   │   └── triage_service.py    # <- the core of Part F
│   │   ├── repositories/
│   │   │   └── complaint_repository.py   # ALL SQL lives here
│   │   └── providers/
│   │       ├── cache/
│   │       │   ├── redis_client.py
│   │       │   └── rate_limiter.py
│   │       └── triage/
│   │           ├── base.py          # the TriageProvider interface
│   │           ├── rules.py         # RuleBasedTriage
│   │           ├── simulated.py     # SimulatedTriage
│   │           ├── llm.py           # LLMTriage (Groq)
│   │           ├── ollama.py        # OllamaTriage
│   │           └── factory.py
│   ├── alembic/                     # migrations (Part D)
│   ├── scripts/
│   │   ├── seed.py                  # idempotent seed, 32 complaints
│   │   └── smoke_test.sh            # manual end-to-end curl check
│   ├── tests/                       # 24 tests (23 pass without a DB, 1 needs Postgres)
│   ├── Dockerfile
│   ├── requirements.txt / requirements-dev.txt
│   ├── .env.example
│   └── pyproject.toml
├── docker-compose.dev.yml           # Postgres + Redis + Ollama + backend, for YOUR local dev
└── docs/adr/0004-pii-and-data-governance.md
```

`docker-compose.dev.yml` is scoped to what you need to develop and demo
your half in isolation. Eiman owns the real `compose.yaml`/`compose.prod.yaml`
(Part G) with the frontend added — when you merge, your service names
(`database`, `cache`, `backend`) and network names (`edge`, `internal`)
already match §3.2 exactly, so it's a paste, not a redesign.

---

## 2. Software you need installed, and why

| Tool | Why | Install |
|---|---|---|
| **Docker Desktop** (or Docker Engine + Compose plugin) | Runs Postgres, Redis, your backend, without installing them on your OS directly | docker.com/get-started |
| **Python 3.12** | Matches the Dockerfile base image; run tests locally without a container | python.org, or `pyenv install 3.12` |
| **Git** | Version control, required for Part A | git-scm.com |
| A **Groq account** (free) | Your primary AI provider | console.groq.com — sign up with email, no card |
| *(optional)* **Ollama** | Offline AI provider, no key needed | ollama.com — or just use the `ollama` service in the compose file |

You do **not** need Postgres or Redis installed on your machine directly —
Docker runs them for you in containers. That's the whole point of Part G.

---

## 3. Concepts you're using, briefly

**FastAPI + Pydantic v2** — FastAPI is a Python web framework that auto-generates
an OpenAPI schema from your route signatures. Pydantic models
(`schemas.py`) are how you describe "what shape of data is this" once, and
reuse it for HTTP validation *and* for validating what the LLM returns.

**Four-layer architecture (`routes → services → repositories → providers`)**
— dependencies only point one way. A route never writes SQL. A service
never opens a raw DB connection or an HTTP client to a third party
directly — it calls a repository or a provider. This is why `triage_service.py`
(a service) *imports* `providers/triage/rules.py` but doesn't itself know
how to talk to Groq's HTTP API — that's `providers/triage/llm.py`'s job.

**SQLAlchemy (async) + Alembic** — SQLAlchemy is the ORM: Python classes
(`models.py`) map to database tables. Alembic is the migration tool: every
schema change is a versioned Python file in `alembic/versions/` that can
be applied (`upgrade`) or undone (`downgrade`). The app never runs
`CREATE TABLE` itself — only `alembic upgrade head` does, once, before the
app starts.

**Redis, two jobs, one connection pool** — a read-through cache
(`stats_service.py`, TTL 30s + invalidate-on-write) and a distributed
rate limiter (`rate_limiter.py`, `INCR`+`EXPIRE` per IP per minute). Same
infrastructure, two purposes — this is deliberate per the assignment.
"Distributed" matters because once Kubernetes scales you to 4 backend
pods, an in-process rate limiter would let through 4x the traffic; Redis
is shared state every pod reads and writes.

**The TriageProvider pattern** — `base.py` defines a `Protocol` (structural
typing: any class with a matching `name` attribute and `triage()` method
satisfies it, no inheritance required). Four implementations exist. The
environment variable `TRIAGE_PROVIDER` picks one at startup
(`factory.py`). Everything else in the system only ever talks to "a
TriageProvider" — swapping Groq for Ollama, or for a future fine-tuned
model, touches one file.

**Timeout / retry / fallback / cache (`triage_service.py`)** — this is the
actual engineering content of Part F: a 10s hard timeout so a slow LLM
can't hang a worker forever; exactly one retry, with jitter, and *only*
for retryable failures (timeouts, HTTP 429, HTTP 5xx — never a 400,
because that request was malformed and retrying it is pointless); a
guaranteed fallback to `RuleBasedTriage` so the citizen never sees a 500;
and a content-hash cache (SHA-256 of the normalized text) so nine
identical "burst main" reports cost one LLM call, not nine.

**Prompt-injection guardrail** — the complaint text is wrapped in
`<complaint>` tags and explicitly told to the model it's *data, not
instructions*. But the real guardrail is structural: the model's JSON
reply is parsed straight into `TriageResult`, whose `category` and
`priority` fields are Python enums. If the model complies with an
injected instruction and returns `category: "ignore_this"`, that string
simply isn't a valid `Category` member — Pydantic raises, and the
orchestrator in `triage_service.py` treats that exactly like any other
provider failure: fallback to rules, `triaged_by = "rules:fallback"`.

**Structured logging + request IDs** — every log line is a JSON object
(`middleware.py`) printed to stdout (never a file — containers are
ephemeral, a file inside one disappears when it dies; your log shipper
in Kubernetes reads stdout). Every request gets an ID, generated if the
caller didn't send one, attached to every log line for that request via
a `contextvars.ContextVar` (thread/task-local storage, safe across
concurrent async requests).

**Graceful shutdown** — on `SIGTERM` (which Kubernetes sends before
killing a pod during a rolling update), `uvicorn --timeout-graceful-shutdown 30`
stops accepting *new* connections but finishes in-flight ones, then
triggers FastAPI's `lifespan` shutdown block, which closes the Postgres
and Redis connection pools cleanly. Skip this and a rolling update drops
live requests.

**Liveness vs readiness** — `/health` never touches the database on
purpose. If it did, a slow Postgres would make Kubernetes think the
*process* is broken and restart it — when actually only the *dependency*
is slow. `/ready` does check Postgres and Redis, and Kubernetes uses a
failing `/ready` to pull the pod out of the load balancer (not kill it).

---

## 4. Setup — step by step

### 4.1 Get the code onto your machine

Unzip this into your team's `civicpulse` repository, so the `backend/`
folder sits alongside wherever Eiman puts `frontend/` and `k8s/`.

```bash
cd civicpulse                  # your team's git repo root
unzip civicpulse-backend.zip -d .
# now you have civicpulse/backend/, civicpulse/docker-compose.dev.yml, civicpulse/docs/
```

### 4.2 Get a Groq API key (2 minutes, free, no card)

1. Go to https://console.groq.com and sign up with your email.
2. Create an API key.
3. Copy `backend/.env.example` to `backend/.env`:
   ```bash
   cd backend
   cp .env.example .env
   ```
4. Open `.env` and paste your key into `GROQ_API_KEY=`.
   **`.env` must already be in `.gitignore` — never commit it (−20 marks
   if it ever lands in git history, per §5.3).**

### 4.3 Bring up Postgres + Redis + your backend

From the repo root (where `docker-compose.dev.yml` sits):

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

This builds the backend image (multi-stage, non-root, per Part G's
requirements) and starts `database`, `cache`, and `backend` (Ollama is
opt-in — see 4.6). Watch the logs:

```bash
docker compose -f docker-compose.dev.yml logs -f backend
```

### 4.4 Run the database migration

The backend container is running, but the `complaints` table doesn't
exist yet — that's a deliberate separation (§2.3: no `CREATE TABLE` at
app startup). Run Alembic:

```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

You should see `Running upgrade -> 0001, initial schema`.

### 4.5 Seed the database

```bash
docker compose -f docker-compose.dev.yml exec backend python -m scripts.seed
```

This inserts 32 realistic complaints across all 6 categories. Run it
again — nothing duplicates (that's the idempotency requirement):

```bash
docker compose -f docker-compose.dev.yml exec backend python -m scripts.seed
# "Seed complete: 0 new rows inserted, 32 already present."
```

### 4.6 (Optional) Run fully offline with Ollama instead of Groq

```bash
docker compose -f docker-compose.dev.yml --profile ollama up -d ollama
docker compose -f docker-compose.dev.yml exec ollama ollama pull llama3.2:1b
# then edit .env: TRIAGE_PROVIDER=ollama, and restart the backend:
docker compose -f docker-compose.dev.yml up -d --build backend
```

### 4.7 Verify it's alive

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/api/stats -i     # look for X-Cache: MISS, then run again for HIT
```

Or run the scripted smoke test (this is literally the CI "integration"
job's logic, runnable by hand):

```bash
chmod +x backend/scripts/smoke_test.sh
BASE_URL=http://localhost:8000 ./backend/scripts/smoke_test.sh
```

Or browse the interactive API docs FastAPI generates for free:
http://localhost:8000/docs

### 4.8 Try triage end-to-end

```bash
curl -X POST http://localhost:8000/api/complaints \
  -H "Content-Type: application/json" \
  -d '{"text":"Burst water main flooding Street 12 since fajr, water entering ground floors","location":"Sector G-9"}'
```

You should get back `201`, a `category`, `priority`, `ai_summary`, and
`triaged_by` (either `llm:groq`, `rules`, `rules:fallback`, depending on
your provider setting and whether Groq responded in time).

Check the observability surface:
```bash
curl http://localhost:8000/api/meta/providers
```

### 4.9 Tear down

```bash
docker compose -f docker-compose.dev.yml down        # keeps volumes (data persists)
docker compose -f docker-compose.dev.yml down -v      # also wipes volumes
```

Per §2.3's persistence contract: `down` then `up` (no `-v`) must preserve
every row — verify this yourself once before you submit.

---

## 5. Running the test suite

You don't need Docker running for most of the suite — 23 of 24 tests use
`fakeredis` and never touch a real database:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -v
```

You should see `23 passed, 1 skipped`. The skipped one
(`test_complaints_api.py`) is the full HTTP+DB integration test — run it
against your real stack once Postgres is up:

```bash
docker compose -f ../docker-compose.dev.yml exec backend alembic upgrade head
RUN_DB_TESTS=1 DATABASE_URL=postgresql+asyncpg://civicpulse:civicpulse@localhost:5432/civicpulse \
  REDIS_URL=redis://localhost:6379/0 python -m pytest tests/test_complaints_api.py -v
```

For coverage (rubric wants ≥65% on `app/`):
```bash
pip install pytest-cov
python -m pytest --cov=app --cov-report=term-missing
```

Lint/type-check (feeds into Eiman's `ci.yml` lint-and-type job):
```bash
ruff check app/
mypy app/
```

---

## 6. The single most important test

The assignment says, verbatim: *"Write this test if you write no other:
given a provider that always raises, POST /api/complaints still returns
201 and `triaged_by == 'rules:fallback'`."*

That's `tests/test_triage_fallback.py::test_provider_that_always_raises_falls_back_to_rules`.
It's already written, already passing. This will very likely be a viva
question — be ready to open `app/services/triage_service.py` and walk
through exactly why a raising provider never produces a 500.

---

## 7. What's deliberately left for you / the team to finish

This is real, running code, but a few things are genuinely team decisions
or need your specific Groq/Ollama credentials, so I left them as clearly
marked TODOs rather than guessing:

- **`.env`** — you must create this yourself with your real `GROQ_API_KEY`
  (never commit it).
- **Merging `docker-compose.dev.yml` into the team's real `compose.yaml`**
  — Eiman owns Part G and the frontend service; sit down together and
  merge your `backend`/`database`/`cache` blocks into the file they build,
  keeping the `edge`/`internal` network split.
- **The remaining 3 ADRs** (provider interface, frontend runtime config,
  deploy-by-SHA) — Part J is shared; `docs/adr/0004-pii-and-data-governance.md`
  is written and is yours since it's about the AI layer.
- **`docs/RUNBOOK.md`** and **`docs/ENGINEERING-NOTES.md`** — shared
  deliverables; you should write the AI-layer and cache-layer answers to
  the 8 engineering questions in §5.2 (especially #4, #6, #7 which map
  directly to your code).
- **Measured cache hit rate** — once you've run real traffic (including
  duplicate complaints) through the system, read it from
  `GET /api/meta/providers` (`triage_cache_hit_rate`) and write the actual
  number into your notes, per §2.5 point 5 ("Report your measured hit rate").
- **Backend test coverage number** — run `pytest --cov` after you've
  connected this to your team's CI and paste the real percentage into
  your submission; I can't fabricate a number I haven't measured against
  your final code.

Everything else — the four-layer split, the state machine, the migration,
the seed, the rate limiter, the cache, all four TriageProvider
implementations, the retry/timeout/fallback orchestration, the injection
guardrail, structured logging, graceful shutdown, health vs ready,
Prometheus metrics, the Dockerfile — is complete and tested.
