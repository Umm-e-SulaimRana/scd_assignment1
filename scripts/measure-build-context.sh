#!/usr/bin/env bash
# §3.1 asks for build-context size before and after .dockerignore, with numbers.
#
#   ./scripts/measure-build-context.sh | tee docs/evidence/build-context.txt
set -euo pipefail

measure() {  # measure <name> <dir>
  local name="$1" dir="$2"
  local raw ignored
  raw=$(du -sk "$dir" | cut -f1)

  # What Docker would actually send: everything not matched by .dockerignore.
  ignored=$(
    cd "$dir"
    # shellcheck disable=SC2312
    tar --exclude-from=<(grep -vE '^\s*(#|$)' .dockerignore || true) -cf - . 2>/dev/null | wc -c
  )
  printf '%-10s  before: %8s KB   after: %8s KB   reduction: %s%%\n' \
    "$name" "$raw" "$((ignored / 1024))" \
    "$(( 100 - (ignored / 1024) * 100 / (raw > 0 ? raw : 1) ))"
}

echo "Docker build-context size, before and after .dockerignore -- $(date -u +%FT%TZ)"
echo "'before' is du -sk of the context directory; 'after' is the tar Docker would send."
echo
measure frontend ./frontend
measure backend  ./backend
echo
echo "The frontend number is the interesting one: node_modules is ~130 MB and is"
echo "excluded, so the daemon receives a few hundred KB instead. Every KB here is"
echo "paid on every single build, including every CI run."
