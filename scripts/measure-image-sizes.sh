#!/usr/bin/env bash
# §3.1: "Report both stage sizes; a frontend image over ~60 MB means the
# multi-stage split is not doing its job."
#
#   ./scripts/measure-image-sizes.sh | tee docs/evidence/image-sizes.txt
set -euo pipefail

echo "Multi-stage image sizes -- $(date -u +%FT%TZ)"
echo

docker build -q --target builder -t civicpulse-frontend:builder ./frontend >/dev/null
docker build -q                  -t civicpulse-frontend:final   ./frontend >/dev/null
docker build -q                  -t civicpulse-backend:final    ./backend  >/dev/null

docker image ls --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' \
  | grep -E 'civicpulse-(frontend|backend)' | sort

echo
echo "Proof the Node toolchain did not survive into the final frontend image:"
echo "\$ docker run --rm --entrypoint sh civicpulse-frontend:final -c 'which node; ls /app 2>&1'"
docker run --rm --entrypoint sh civicpulse-frontend:final -c 'which node || echo "  node: not present"; ls /app 2>&1 || true'

echo
echo "And that neither image runs as root:"
for img in civicpulse-frontend:final civicpulse-backend:final; do
  printf '  %-28s runs as: ' "$img"
  docker run --rm --entrypoint sh "$img" -c 'id -un'
done
