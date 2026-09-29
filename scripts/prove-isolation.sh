#!/usr/bin/env bash
# §3.2: "docker compose exec frontend ping database MUST fail."
#
# A failing command as evidence of correct design. Run this with the stack up,
# tee the output into docs/evidence/, and show it in the demo video.
#
#   ./scripts/prove-isolation.sh | tee docs/evidence/network-isolation.txt
set -uo pipefail

COMPOSE="${COMPOSE:-docker compose}"
pass=0; fail=0

check() {  # check <description> <expected: ok|blocked> <command...>
  local desc="$1" expect="$2"; shift 2
  echo "--- $desc"
  echo "\$ $*"
  if "$@" >/tmp/isolation.out 2>&1; then actual=ok; else actual=blocked; fi
  sed 's/^/    /' /tmp/isolation.out | head -6
  if [[ "$actual" == "$expect" ]]; then
    echo "    => $actual (expected $expect)  PASS"; pass=$((pass+1))
  else
    echo "    => $actual (expected $expect)  FAIL"; fail=$((fail+1))
  fi
  echo
}

echo "CivicPulse network segmentation check -- $(date -u +%FT%TZ)"
echo "Topology: frontend=[edge]  backend=[edge,internal]  database,cache=[internal, internal:true]"
echo

# The one the rubric names. The frontend is the internet-facing component and
# therefore the most likely to be compromised; it must have no route to the data.
check "frontend -> database (must be blocked)" blocked \
  $COMPOSE exec -T frontend sh -c 'nc -z -w 3 database 5432'

check "frontend -> cache (must be blocked)" blocked \
  $COMPOSE exec -T frontend sh -c 'nc -z -w 3 cache 6379'

# The backend is the only service on both networks, so it is the only path in.
check "backend -> database (must work)" ok \
  $COMPOSE exec -T backend python -c "import socket;socket.create_connection(('database',5432),3)"

check "backend -> cache (must work)" ok \
  $COMPOSE exec -T backend python -c "import socket;socket.create_connection(('cache',6379),3)"

# internal: true means no route out. This is the trade-off in engineering
# note #7: it is also why the LLM provider has to be called from the backend,
# which is on edge, and not from anything that lives only on internal.
check "database -> internet (must be blocked by internal: true)" blocked \
  $COMPOSE exec -T database sh -c 'wget -q -T 4 -O /dev/null https://api.groq.com'

check "frontend -> backend (must work)" ok \
  $COMPOSE exec -T frontend sh -c 'wget -q -T 4 -O /dev/null http://backend:8000/health'

echo "=============================="
echo "pass: $pass   fail: $fail"
[[ $fail -eq 0 ]] || exit 1
